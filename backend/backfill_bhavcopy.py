"""
backfill_bhavcopy.py — seed NSE bhavcopy history for the factor model (factor_service).

Downloads the last N trading days' security-wise bhavcopy via Scrapling (bhavcopy_service._download),
skipping weekends and files already on disk. NSE holidays simply return no file (counted as 'failed').
One-time seed, or schedule daily. Forward days accrue automatically via compute_technicals.

Usage:  python backfill_bhavcopy.py [N_TRADING_DAYS=120]
"""
import os
import sys
import time
import logging
from datetime import timedelta

import bhavcopy_service as bhav

logging.basicConfig(level=logging.WARNING)


def _exists(d) -> bool:
    return any(os.path.exists(os.path.join(f, bhav._fname(d))) for f in (bhav._DIR, bhav._ALT_DIR))


def main(n: int = 120):
    d = bhav._last_trading_day()
    got = skipped = failed = 0
    checked = 0
    # bound the walk so a long holiday stretch can't loop forever
    while (got + skipped) < n and checked < n * 2:
        checked += 1
        if d.weekday() < 5:                      # weekday only
            if _exists(d):
                skipped += 1
            elif bhav._download(d):
                got += 1
                print(f"  {d}  downloaded")
                time.sleep(0.5)                  # be polite to NSE archives
            else:
                failed += 1
                print(f"  {d}  no file (holiday / not published)")
        d -= timedelta(days=1)
    print(f"backfill done: downloaded={got}  skipped(existing)={skipped}  missing={failed}")
    return got


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 120)
