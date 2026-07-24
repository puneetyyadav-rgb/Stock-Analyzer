import sys
import os
import json
import asyncio
from dotenv import load_dotenv
load_dotenv(r'E:\Website\Stock Analysis\stock ticker v2\backend\.env')
from google import genai
from google.genai import types

sys.path.append(r'E:\Website\Stock Analysis\stock ticker v2\backend')
from extra_service import get_concalls, fetch_pdf_text

# Pinned model and settings
MODEL = "gemini-3.5-flash-lite"
TEMPERATURE = 0.0

SEGMENTATION_PROMPT = """You are a financial NLP parser.
Your task is to identify the exact boundary between 'Prepared Remarks' (Management's opening statements) and the 'Q&A' (Questions and Answers) section in the provided earnings call transcript.
Look for phrases like 'We will now begin the Q&A session', 'open the floor for questions', or 'moderator, over to you'.
Output ONLY a strict JSON object with no markdown:
{
  "boundary_phrase": "The exact sentence where the transition happens",
  "prepared_remarks_text": "The full text of the prepared remarks (approximate summary if too long, or just first few and last few sentences if you can't output it all, BUT ideally return as much text as possible. Since there's a token limit, you MUST return the exact substring of the last 100 words of prepared remarks and the first 100 words of Q&A)",
  "prepared_remarks_excerpt": "Last 50 words of prepared remarks",
  "qa_excerpt": "First 50 words of Q&A"
}"""

SCORING_PROMPT = """You are a Quantitative NLP scoring engine for Indian equities.
Analyze the provided segment of an earnings call transcript and compute a sentiment score and hesitation index.
Look for hesitation words (e.g. 'challenging macro', 'limited visibility', 'subject to', 'working through', 'deferred').
Output ONLY a strict JSON object with no markdown:
{
  "sentiment_score": a float between -1.0 (extremely bearish) and 1.0 (extremely bullish),
  "hesitation_index": a float between 0.0 and 100.0 representing the frequency of hedging/uncertainty phrases,
  "key_hedging_phrases_found": ["phrase 1", "phrase 2"]
}"""

def get_client():
    key = os.environ.get("GEMINI_API_KEY")
    return genai.Client(api_key=key) if key else None

async def run_llm(client, prompt, text):
    content = f"{prompt}\n\nTranscript Segment:\n{text[:20000]}"
    config = types.GenerateContentConfig(temperature=TEMPERATURE, response_mime_type="application/json")
    try:
        resp = await asyncio.to_thread(client.models.generate_content, model=MODEL, contents=content, config=config)
        return json.loads(resp.text.strip())
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        return {"error": str(e)}

async def process_transcript(client, symbol, date_str, text):
    print(f"\nProcessing {symbol} ({date_str}) - Length: {len(text)} chars")
    
    # 1. Segmentation
    print("  -> Running Segmentation...")
    seg_result = await run_llm(client, SEGMENTATION_PROMPT, text)
    
    if "error" in seg_result:
        print("  -> Segmentation failed")
        return {"symbol": symbol, "date": date_str, "error": seg_result}
    
    boundary = seg_result.get("boundary_phrase") or ""
    print(f"  -> Found boundary: {boundary[:100]}...")
    
    prepared_text = text
    qa_text = ""
    if boundary and boundary in text:
        parts = text.split(boundary, 1)
        prepared_text = parts[0]
        qa_text = parts[1]
    else:
        mid = len(text) // 2
        prepared_text = text[:mid]
        qa_text = text[mid:]
        
    # 2. Scoring
    print("  -> Running Sentiment/Hesitation Scoring on Prepared Remarks...")
    prep_score = await run_llm(client, SCORING_PROMPT, prepared_text)
    
    print("  -> Running Sentiment/Hesitation Scoring on Q&A...")
    qa_score = await run_llm(client, SCORING_PROMPT, qa_text)
    
    s_prep = prep_score.get("sentiment_score", 0.0)
    s_qa = qa_score.get("sentiment_score", 0.0)
    divergence = s_qa - s_prep if isinstance(s_qa, (int,float)) and isinstance(s_prep, (int,float)) else 0.0
    
    return {
        "symbol": symbol,
        "date": date_str,
        "segmentation_boundary": boundary,
        "prepared_remarks": prep_score,
        "qa": qa_score,
        "divergence": divergence
    }

async def main():
    client = get_client()
    if not client:
        print("No GEMINI_API_KEY")
        return
        
    stocks = ["INFY", "RELIANCE"]
    results = []
    
    # Create local caching directory
    cache_dir = r'E:\Website\Stock Analysis\stock ticker v2\MISC\transcripts'
    os.makedirs(cache_dir, exist_ok=True)
    
    for sym in stocks:
        print(f"\nFetching concalls for {sym}...")
        concalls = get_concalls(sym)
        count = 0
        for cc in concalls:
            if not cc.get("transcript"): continue
            if count >= 8: break # 8 quarters backtest
            
            url = cc["transcript"]
            date_str = cc["date"]
            
            # Safe filename
            safe_date = date_str.replace(" ", "_").replace(",", "")
            cache_file = os.path.join(cache_dir, f"{sym}_{safe_date}.txt")
            
            text = ""
            if os.path.exists(cache_file):
                print(f"  -> Loading cached transcript from {cache_file}")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    text = f.read()
            else:
                print(f"  -> Downloading fresh PDF: {url}")
                text = fetch_pdf_text(url)
                if len(text) > 500:
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        f.write(text)
            
            if len(text) > 500:
                # 15 RPM throttling (4.5s pause between transcripts)
                await asyncio.sleep(4.5)
                res = await process_transcript(client, sym, date_str, text)
                results.append(res)
                count += 1
                
    output_path = r'E:\Website\Stock Analysis\stock ticker v2\MISC\phase0_validation_results.json'
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved results to {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
