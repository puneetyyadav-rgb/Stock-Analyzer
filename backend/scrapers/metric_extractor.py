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
        # Example implementation of uploading the file
        uploaded_file = client.files.upload(file=pdf_path)
        
        prompt = """
        You are a senior banking analyst. Read this quarterly investor presentation.
        Extract the following metrics exactly as they appear for the latest quarter:
        1. Gross NPA % (GNPA)
        2. Net NPA % (NNPA)
        3. Provision Coverage Ratio % (PCR)
        4. CASA Ratio % (CASA)
        5. Capital Adequacy Ratio % (CRAR)
        6. Credit Cost % (creditCost_pct)
        7. Slippage Ratio % (slippage_pct)
        8. Restructured Book % (restructuredBook_pct)
        9. Segment Split / Retail vs Corporate (segmentSplit)
        10. Geographic Concentration (geographicConcentration)
        
        If a metric is missing, return null for it.
        Return ONLY valid JSON matching this schema:
        {
            "GNPA": float | null,
            "NNPA": float | null,
            "PCR": float | null,
            "CASA": float | null,
            "CRAR": float | null,
            "creditCost_pct": float | null,
            "slippage_pct": float | null,
            "restructuredBook_pct": float | null,
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
        uploaded_file.delete()
        
        return json.loads(response.text)

    except Exception as e:
        logger.error("Gemini Extraction Failed: %s", e)
        return {}

if __name__ == "__main__":
    # Test script usage
    print("Metric Extractor Module Initialized.")
