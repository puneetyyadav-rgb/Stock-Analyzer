import os
import json
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

def extract_bfsi_metrics_from_pdf(pdf_path: str) -> dict:
    """
    Uses Gemini Vision to read the PDF and extract Phase-2 banking metrics.
    """
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        logger.error("GEMINI_API_KEY not found in environment.")
        return {}

    client = genai.Client(api_key=key)

    # In production, we upload the PDF to Gemini via the Files API
    # For this architecture, we assume the PDF is uploaded and processed
    try:
        # Upload the file
        uploaded_file = client.files.upload(file=pdf_path)
        
        # Poll until the file is ACTIVE (PDF processing can take a few seconds)
        import time
        while uploaded_file.state.name == "PROCESSING":
            logger.info("Waiting for PDF to be processed by Gemini...")
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)
            
        if uploaded_file.state.name == "FAILED":
            logger.error("Gemini failed to process the PDF file.")
            client.files.delete(name=uploaded_file.name)
            return {}
        
        prompt = """
        You are a senior banking analyst. Read this quarterly financial document (it may be an investor presentation or a detailed financial results release).
        Extract the following metrics exactly as they appear for the latest quarter:
        1. Gross NPA % (GNPA)
        2. Net NPA % (NNPA)
        3. Provision Coverage Ratio % (PCR)
        4. CASA Ratio % (CASA)
        5. Capital Adequacy Ratio % (CRAR)
        6. Credit Cost % (creditCost_pct)
        7. Slippage Ratio % (slippage_pct)
        8. Restructured Book % (restructuredBook_pct)
        9. Collateral / Security Coverage % (securityCoverage_pct)
        10. Segment Split / Retail vs Corporate (segmentSplit)
        11. Geographic Concentration (geographicConcentration)
        
        If a metric is missing, return null for it.
        Return ONLY valid JSON matching this schema:
        {
            "Reasoning": "Brief explanation of where you found the data or why it is missing",
            "GNPA": float | null,
            "NNPA": float | null,
            "PCR": float | null,
            "CASA": float | null,
            "CRAR": float | null,
            "creditCost_pct": float | null,
            "slippage_pct": float | null,
            "restructuredBook_pct": float | null,
            "securityCoverage_pct": float | null,
            "segmentSplit": string | null,
            "geographicConcentration": string | null
        }
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[uploaded_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        
        # Cleanup the file from Google's servers
        client.files.delete(name=uploaded_file.name)
        
        return json.loads(response.text)

    except Exception as e:
        logger.error("Gemini Extraction Failed: %s", e)
        return {}

def extract_transcript_metrics_from_pdf(pdf_path: str) -> dict:
    key = os.environ.get("GEMINI_API_KEY")
    if not key: return {}
    client = genai.Client(api_key=key)
    try:
        uploaded_file = client.files.upload(file=pdf_path)
        import time
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)
            
        if uploaded_file.state.name == "FAILED":
            client.files.delete(name=uploaded_file.name)
            return {}
            
        prompt = """
        You are a senior banking analyst reading an earnings call transcript.
        Extract the following metrics explicitly mentioned by management during the call:
        1. Provision Coverage Ratio % (PCR)
        2. Slippage Ratio % (or total slippages)
        3. Restructured Book % (or total restructured assets)
        
        Return ONLY valid JSON matching this schema:
        {
            "PCR": float | null,
            "slippage_pct": float | null,
            "restructuredBook_pct": float | null
        }
        """
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[uploaded_file, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        client.files.delete(name=uploaded_file.name)
        return json.loads(response.text)
    except Exception as e:
        logger.error("Transcript Extraction Failed: %s", e)
        return {}

def extract_annual_report_metrics_from_pdf(pdf_path: str) -> dict:
    key = os.environ.get("GEMINI_API_KEY")
    if not key: return {}
    client = genai.Client(api_key=key)
    try:
        uploaded_file = client.files.upload(file=pdf_path)
        import time
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(5)
            uploaded_file = client.files.get(name=uploaded_file.name)
            
        if uploaded_file.state.name == "FAILED":
            client.files.delete(name=uploaded_file.name)
            return {}
            
        prompt = """
        You are a senior banking analyst reading an Annual Report.
        Extract the following institutional risk and liquidity metrics for the most recent fiscal year:
        1. Liquidity Coverage Ratio % (LCR_pct)
        2. Net Stable Funding Ratio % (NSFR_pct)
        3. Tier 1 Capital % (Tier1Capital_pct)
        4. Common Equity Tier 1 % (CET1_pct)
        5. Leverage Ratio % (leverageRatio_pct)
        6. Return on Risk-Weighted Assets % (roRWA_pct) - NOTE: If not explicitly stated, calculate it as (Net Profit / Total Risk Weighted Assets) * 100.
        7. Asset-Liability Duration Mismatch (ALM_mismatch) - NOTE: If a specific quantitative mismatch is not available, provide a brief string summarizing the maturity gap analysis or liquidity mismatch.
        
        Return ONLY valid JSON matching this schema:
        {
            "LCR_pct": float | null,
            "NSFR_pct": float | null,
            "Tier1Capital_pct": float | null,
            "CET1_pct": float | null,
            "leverageRatio_pct": float | null,
            "roRWA_pct": float | null,
            "ALM_mismatch": string | null
        }
        """
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[uploaded_file, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        client.files.delete(name=uploaded_file.name)
        return json.loads(response.text)
    except Exception as e:
        logger.error("Annual Report Extraction Failed: %s", e)
        return {}

if __name__ == "__main__":
    # Test script usage
    print("Metric Extractor Module Initialized.")
