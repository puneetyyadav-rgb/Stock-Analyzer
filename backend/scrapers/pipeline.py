import os
import logging
from dotenv import load_dotenv
load_dotenv()

from scrapers.database import get_latest_metrics, save_metric
from scrapers.nse_scraper import (
    fetch_nse_investor_presentations,
    fetch_nse_earnings_transcripts,
    fetch_nse_annual_reports,
    download_nse_pdf
)
from scrapers.metric_extractor import (
    extract_bfsi_metrics_from_pdf,
    extract_transcript_metrics_from_pdf,
    extract_annual_report_metrics_from_pdf
)

logger = logging.getLogger(__name__)

def run_scraper_pipeline(symbol: str):
    """
    Orchestrates the 3 scraper modules:
    1. Checks if we already have the data in the database.
    2. Uses NSE Scraper to find and download the latest Investor Presentation PDF.
    3. Uses Gemini Extractor to read the PDF and extract GNPA, PCR, etc.
    4. Saves the extracted metrics into the Database.
    """
    logger.info("--- Starting Scraper Pipeline for %s ---", symbol)
    
    # Step 1: Check Database
    existing = get_latest_metrics(symbol)
    if existing and "GNPA" in existing and "PCR" in existing and "LCR_pct" in existing:
        # Only skip if we have at least one key from all 3 pipelines (simplified check)
        logger.info("Comprehensive metrics already exist in database for %s. Skipping scrape.", symbol)
        return existing
        
    unified_metrics = {}
        
    # --- PIPELINE 1: Financial Results ---
    logger.info("Fetching Financial Results from NSE...")
    items_fr = fetch_nse_investor_presentations(symbol, months_back=6)
    if items_fr:
        att_fr = items_fr[0].get("attchmntFile") or items_fr[0].get("attachment")
        logger.info("Downloading Financial Results PDF: %s", att_fr)
        pdf_path_fr = download_nse_pdf(symbol, att_fr)
        if pdf_path_fr:
            logger.info("Extracting Financial Results...")
            metrics_fr = extract_bfsi_metrics_from_pdf(pdf_path_fr)
            if metrics_fr:
                unified_metrics.update(metrics_fr)
                
    # --- PIPELINE 2: Earnings Call Transcripts ---
    logger.info("Fetching Earnings Call Transcripts from NSE...")
    items_tr = fetch_nse_earnings_transcripts(symbol, months_back=6)
    if items_tr:
        att_tr = items_tr[0].get("attchmntFile") or items_tr[0].get("attachment")
        logger.info("Downloading Transcript PDF: %s", att_tr)
        pdf_path_tr = download_nse_pdf(symbol, att_tr)
        if pdf_path_tr:
            logger.info("Extracting Transcript metrics...")
            metrics_tr = extract_transcript_metrics_from_pdf(pdf_path_tr)
            if metrics_tr:
                unified_metrics.update(metrics_tr)
                
    # --- PIPELINE 3: Annual Reports (for Basel III Pillar 3) ---
    logger.info("Fetching Annual Report from NSE...")
    items_ar = fetch_nse_annual_reports(symbol)
    if items_ar:
        att_ar = items_ar[0].get("fileName")
        logger.info("Downloading Annual Report PDF: %s", att_ar)
        pdf_path_ar = download_nse_pdf(symbol, att_ar)
        if pdf_path_ar:
            logger.info("Extracting Basel III metrics from Annual Report...")
            metrics_ar = extract_annual_report_metrics_from_pdf(pdf_path_ar)
            if metrics_ar:
                unified_metrics.update(metrics_ar)
    
    if not unified_metrics:
        logger.error("Failed to extract any metrics across all pipelines for %s", symbol)
        return existing or None
        
    logger.info("Successfully extracted unified metrics: %s", unified_metrics)
    
    # Save to Database
    logger.info("Saving unified metrics to SQLite Database...")
    quarter_label = "Latest Quarter"
    for key, value in unified_metrics.items():
        if key != "Reasoning" and value is not None:
            # We don't save 'Reasoning' to DB, but we could. We'll pass "unified" as pdf_path
            save_metric(symbol, quarter_label, key, value, "unified_pipeline")
            
    logger.info("--- Scraper Pipeline Complete for %s ---", symbol)
    
    # Return merged dict (prefer newly scraped, fallback to existing)
    if existing:
        existing.update(unified_metrics)
        return existing
    return unified_metrics

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Test the full pipeline on HDFC Bank!
    run_scraper_pipeline("HDFCBANK.NS")
