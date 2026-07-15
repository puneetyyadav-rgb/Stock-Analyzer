"""Catalyst Archive Service (Phase 1 — Archive Backfill).
Stores 24-month historical corporate disclosures (NSE/BSE) and earnings concall transcripts
locally in SQLite (backend/data/catalyst_archive.db) with automatic PDF text extraction.
"""
import os
import io
import json
import sqlite3
import logging
import urllib.parse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from extra_service import _nse_session, _strip_symbol

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "catalyst_archive.db")


def get_db_connection() -> sqlite3.Connection:
    """Returns a connected SQLite session with Row factory enabled."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_archive_db() -> None:
    """Initializes tables and unique constraints for announcements and concalls archive."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS announcements_archive (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    source TEXT NOT NULL,
                    announcement_id TEXT NOT NULL,
                    subject TEXT,
                    full_text TEXT,
                    attachment_url TEXT,
                    date_published TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(symbol, announcement_id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ann_sym ON announcements_archive(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ann_date ON announcements_archive(date_published)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS concalls_archive (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    quarter_label TEXT NOT NULL,
                    full_text TEXT,
                    date_published TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(symbol, quarter_label)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conc_sym ON concalls_archive(symbol)")
    finally:
        conn.close()


def _extract_pdf_text_sync(pdf_bytes: bytes) -> str:
    """Extracts clean text from raw PDF bytes using pypdf."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text_parts = []
        # Read up to first 8 pages to avoid excessive memory/time on massive annual reports
        for page in reader.pages[:8]:
            extracted = page.extract_text()
            if extracted:
                text_parts.append(extracted.strip())
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.warning(f"Failed to extract text from PDF bytes: {e}")
        return ""


def _download_and_extract_pdf(url: str, session) -> str:
    """Downloads an announcement PDF attachment and extracts body text."""
    if not url:
        return ""
    try:
        # Handle relative URLs from NSE
        if url.startswith("/"):
            url = f"https://www.nseindia.com{url}"
        elif not url.startswith("http"):
            url = f"https://archives.nseindia.com/content/equities/{url}"

        r = session.get(url, timeout=12)
        if r.status_code == 200 and len(r.content) > 100:
            text = _extract_pdf_text_sync(r.content)
            return text
    except Exception as e:
        logger.debug(f"PDF download/extract skipped for {url}: {e}")
    return ""


def archive_nse_announcements(
    symbol: str,
    months_back: int = 24,
    download_pdfs: bool = True,
    max_items: int = 500
) -> Dict[str, int]:
    """Fetches up to 24 months of NSE corporate announcements for `symbol`, extracts PDF body text
    where available, and stores deduplicated rows into local SQLite archive.
    Returns stats dict: {'fetched': N, 'inserted': M, 'updated': K}.
    """
    init_archive_db()
    clean_sym = _strip_symbol(symbol)
    session = _nse_session()

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=int(months_back * 30.4))
    from_str = start_dt.strftime("%d-%m-%Y")
    to_str = end_dt.strftime("%d-%m-%Y")

    url = f"https://www.nseindia.com/api/corporate-announcements?index=equities&symbol={clean_sym}&from_date={from_str}&to_date={to_str}"
    logger.info(f"Archiving NSE announcements for {clean_sym} ({from_str} -> {to_str})...")

    try:
        r = session.get(url, timeout=15)
        if r.status_code != 200:
            logger.warning(f"NSE corporate announcements API returned HTTP {r.status_code} for {clean_sym}")
            return {"fetched": 0, "inserted": 0, "updated": 0}
        data = r.json()
        items = data if isinstance(data, list) else data.get("data", [])
    except Exception as e:
        logger.error(f"Error fetching NSE announcements for {clean_sym}: {e}")
        return {"fetched": 0, "inserted": 0, "updated": 0}

    if not items:
        return {"fetched": 0, "inserted": 0, "updated": 0}

    # Slice up to max_items if needed
    items = items[:max_items]
    stats = {"fetched": len(items), "inserted": 0, "updated": 0}

    conn = get_db_connection()
    try:
        for item in items:
            subject = item.get("subject") or item.get("desc") or ""
            date_pub = item.get("an_dt") or item.get("date") or ""
            attachment = item.get("attchmntFile") or item.get("attachment") or ""

            # Build a stable unique ID for this announcement
            # Use seq_id or timestamp + subject hash
            ann_id = str(item.get("seq_id") or item.get("sm_id") or "")
            if not ann_id:
                ann_id = f"{date_pub}_{hash(subject) % 100000000}"

            # Check if already in DB
            cursor = conn.execute(
                "SELECT id, subject, full_text FROM announcements_archive WHERE symbol = ? AND announcement_id = ?",
                (clean_sym, ann_id)
            )
            existing = cursor.fetchone()

            if existing:
                # If existing record only has subject text and we want to download PDFs, try upgrading it
                ex_text = str(existing["full_text"] or "")
                ex_subj = str(existing["subject"] or "")
                if download_pdfs and attachment and (not ex_text or ex_text == ex_subj or len(ex_text) <= len(ex_subj) + 10):
                    pdf_text = _download_and_extract_pdf(attachment, session)
                    if pdf_text and len(pdf_text) > len(ex_subj) + 10:
                        with conn:
                            conn.execute(
                                "UPDATE announcements_archive SET full_text = ? WHERE id = ?",
                                (pdf_text, existing["id"])
                            )
                        stats["updated"] += 1
                continue

            # Not existing — extract PDF if enabled and available, otherwise use subject
            full_text = ""
            if download_pdfs and attachment:
                full_text = _download_and_extract_pdf(attachment, session)
            
            if not full_text:
                full_text = subject

            with conn:
                conn.execute("""
                    INSERT OR IGNORE INTO announcements_archive (
                        symbol, source, announcement_id, subject, full_text,
                        attachment_url, date_published, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    clean_sym,
                    "NSE",
                    ann_id,
                    subject,
                    full_text,
                    attachment,
                    date_pub,
                    datetime.now().isoformat()
                ))
                stats["inserted"] += 1

    finally:
        conn.close()

    logger.info(f"Archived {clean_sym}: Fetched {stats['fetched']}, Inserted {stats['inserted']}, Updated {stats['updated']} rows.")
    return stats


def get_archived_announcements(
    symbol: Optional[str] = None,
    limit: int = 100,
    only_with_text: bool = False
) -> List[Dict]:
    """Retrieves stored historical announcements from local SQLite archive."""
    init_archive_db()
    conn = get_db_connection()
    try:
        query = "SELECT * FROM announcements_archive"
        params = []
        conditions = []
        if symbol:
            conditions.append("symbol = ?")
            params.append(_strip_symbol(symbol))
        if only_with_text:
            conditions.append("full_text IS NOT NULL AND full_text != ''")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


CURRENT_SCAN_PROGRESS = {
    "is_scanning": False,
    "current_stock": "",
    "scanned_count": 0,
    "total_stocks": 0,
    "filter_type": "all",
    "disclosures_found": 0,
    "catalysts_extracted": 0,
    "status_msg": "Idle"
}


def archive_nse_universe_batch(
    symbols: Optional[List[str]] = None,
    months_back: int = 3,
    download_pdfs: bool = False,
    max_items_per_stock: int = 15,
    max_stocks: int = 2050,
    delay_sec: float = 0.3,
    universe_filter: str = "all"
) -> Dict[str, Any]:
    """Batch archives NSE corporate announcements across active Indian equity symbols
    from local Bhavcopy/MASTER list.
    `universe_filter` can be 'all' (2,029 stocks), 'micro_only' (1,879 small/micro-caps outside Nifty 200), or 'benchmark_only' (~150 large/midcaps).
    Returns market-wide extraction summary stats.
    """
    import time
    if symbols is None:
        try:
            from train_nse_qlib import load_symbols_from_bhavcopy_if_available, MASTER_NSE_UNIVERSE
            all_syms = load_symbols_from_bhavcopy_if_available()
            master_set = {s.replace(".NS", "").strip().upper() for s in MASTER_NSE_UNIVERSE}

            if universe_filter == "micro_only":
                symbols = [s for s in all_syms if s.replace(".NS", "").strip().upper() not in master_set]
            elif universe_filter == "benchmark_only":
                symbols = [s for s in all_syms if s.replace(".NS", "").strip().upper() in master_set]
            else:
                symbols = all_syms

            symbols = symbols[:max_stocks]
        except Exception:
            symbols = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "ITC", "BHARTIARTL", "LT", "WIPRO"]

    logger.info(f"Starting market-wide corporate announcement archive across {len(symbols)} Indian symbols (filter: {universe_filter})...")
    total_stats = {"stocks_scanned": 0, "fetched": 0, "inserted": 0, "updated": 0, "errors": 0}

    CURRENT_SCAN_PROGRESS["is_scanning"] = True
    CURRENT_SCAN_PROGRESS["total_stocks"] = len(symbols)
    CURRENT_SCAN_PROGRESS["scanned_count"] = 0
    CURRENT_SCAN_PROGRESS["filter_type"] = universe_filter
    CURRENT_SCAN_PROGRESS["disclosures_found"] = 0
    CURRENT_SCAN_PROGRESS["status_msg"] = f"Initializing scan across {len(symbols)} stocks ({universe_filter})..."

    for i, sym in enumerate(symbols):
        CURRENT_SCAN_PROGRESS["current_stock"] = sym
        CURRENT_SCAN_PROGRESS["scanned_count"] = i + 1
        CURRENT_SCAN_PROGRESS["status_msg"] = f"Scanning {i+1}/{len(symbols)} stocks (`{sym}`). Found {total_stats['inserted']} new disclosures."
        try:
            res = archive_nse_announcements(
                symbol=sym,
                months_back=months_back,
                download_pdfs=download_pdfs,
                max_items=max_items_per_stock
            )
            total_stats["stocks_scanned"] += 1
            total_stats["fetched"] += res.get("fetched", 0)
            total_stats["inserted"] += res.get("inserted", 0)
            total_stats["updated"] += res.get("updated", 0)
            CURRENT_SCAN_PROGRESS["disclosures_found"] = total_stats["inserted"]
            CURRENT_SCAN_PROGRESS["status_msg"] = f"Scanned {i+1}/{len(symbols)} stocks (`{sym}`). Found {total_stats['inserted']} new disclosures."
        except Exception as e:
            logger.warning(f"Error batch archiving {sym}: {e}")
            total_stats["errors"] += 1

        if delay_sec > 0:
            time.sleep(delay_sec)

    # Automatically run Phase 2 deterministic extraction over the updated archive
    CURRENT_SCAN_PROGRESS["status_msg"] = f"Extracting future catalyst dates & snippets from {total_stats['inserted']} disclosures..."
    try:
        from events_service import run_catalyst_extraction
        ext_stats = run_catalyst_extraction(symbol=None, days_forward=365)
        total_stats["catalysts_extracted"] = ext_stats.get("extracted", 0)
        total_stats["catalysts_inserted"] = ext_stats.get("inserted", 0)
        CURRENT_SCAN_PROGRESS["catalysts_extracted"] = ext_stats.get("extracted", 0)
    except Exception as e:
        logger.error(f"Error running post-batch Phase 2 catalyst extraction: {e}")

    CURRENT_SCAN_PROGRESS["is_scanning"] = False
    CURRENT_SCAN_PROGRESS["status_msg"] = f"Scan complete! Scanned {len(symbols)} stocks ({universe_filter}). Found {total_stats['inserted']} disclosures & {total_stats.get('catalysts_extracted', 0)} future catalysts."
    logger.info(f"Market-Wide Archive Complete across {total_stats['stocks_scanned']} stocks: {total_stats}")
    return total_stats

