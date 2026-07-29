import os
import logging
from scrapers.database import get_latest_metrics, save_metric
from scrapers.nse_scraper import fetch_nse_investor_presentations, download_nse_pdf
from scrapers.metric_extractor import extract_bfsi_metrics_from_pdf

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
    if existing and "GNPA" in existing:
        logger.info("Metrics already exist in database for %s. Skipping scrape.", symbol)
        return existing
        
    # Step 2: Fetch PDF via NSE Scraper
    logger.info("No data in DB. Fetching latest presentation from NSE...")
    items = fetch_nse_investor_presentations(symbol, months_back=6)
    
    if not items:
        logger.error("No investor presentations found on NSE for %s in the last 6 months.", symbol)
        return None
        
    top_item = items[0]
    attachment_url = top_item.get("attchmntFile") or top_item.get("attachment")
    quarter_label = top_item.get("subject", "Latest Quarter")[:30] # Just a stub for the quarter
    
    logger.info("Downloading PDF: %s", attachment_url)
    pdf_path = download_nse_pdf(symbol, attachment_url)
    
    if not pdf_path:
        logger.error("Failed to download PDF for %s", symbol)
        return None
        
    # Step 3: Extract Metrics via Gemini
    logger.info("PDF downloaded to %s. Sending to Gemini for extraction...", pdf_path)
    metrics = extract_bfsi_metrics_from_pdf(pdf_path)
    
    if not metrics:
        logger.error("Gemini failed to extract any metrics from the PDF.")
        return None
        
    logger.info("Successfully extracted metrics: %s", metrics)
    
    # Step 4: Save to Database
    logger.info("Saving metrics to SQLite Database...")
    for key, value in metrics.items():
        if value is not None:
            save_metric(symbol, quarter_label, key, value, pdf_path)
            
    logger.info("--- Scraper Pipeline Complete for %s ---", symbol)
    return metrics

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Test the full pipeline on HDFC Bank!
    run_scraper_pipeline("HDFCBANK.NS")
