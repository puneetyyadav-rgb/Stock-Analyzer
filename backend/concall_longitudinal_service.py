import os
import json
import asyncio
import logging
from typing import Dict, Any, List
import google.generativeai as genai

# Append backend path if run independently
import sys
sys.path.append(r'E:\Website\Stock Analysis\stock ticker v2\backend')

from extra_service import get_concalls, fetch_pdf_text
from dotenv import load_dotenv

load_dotenv()

# Track which key index we are on
current_key_idx = 0
all_keys = [os.environ.get("GEMINI_API_KEY")]
backup_keys_str = os.environ.get("GEMINI_BACKUP_KEYS", "")
if backup_keys_str:
    all_keys.extend([k.strip() for k in backup_keys_str.split(",") if k.strip()])

genai.configure(api_key=all_keys[0])

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

STORE_PATH = r'E:\Website\Stock Analysis\stock ticker v2\MISC\concall_longitudinal_store.json'
PROMPT_PATH = r'E:\Website\Stock Analysis\stock ticker v2\MISC\concall_synthesizer_system_prompt.md'

with open(PROMPT_PATH, 'r', encoding='utf-8') as f:
    content = f.read()
    # Extract just the prompt part (between the first ``` and the second ```)
    try:
        SYSTEM_PROMPT = content.split("```")[1].strip()
    except IndexError:
        SYSTEM_PROMPT = content # fallback

def _load_store() -> dict:
    if os.path.exists(STORE_PATH):
        try:
            with open(STORE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def _save_store(store: dict):
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)

async def generate_longitudinal_synthesis(symbol: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Fetches the last 8 quarters of concall PDFs, sends them all to Gemini 1.5 Flash
    for a 2-year longitudinal analysis, and caches the result.
    """
    store = _load_store()
    
    # Check cache first
    if not force_refresh and symbol in store:
        logger.info(f"[{symbol}] Returning cached longitudinal synthesis.")
        return store[symbol]
        
    logger.info(f"[{symbol}] Starting 8-Quarter Longitudinal Synthesis...")
    
    # 1. Get the list of concall PDFs
    all_concalls = get_concalls(symbol)
    if not all_concalls:
        return {"error": f"No concall data found for {symbol}"}
        
    # Take up to the last 8
    target_concalls = all_concalls[:8]
    # Reverse so they are chronological (oldest to newest) as Claude requested
    target_concalls.reverse()
    
    logger.info(f"[{symbol}] Found {len(target_concalls)} recent quarters to analyze.")
    
    # 2. Extract text from each PDF (check local folder first)
    combined_transcript_text = ""
    for idx, c in enumerate(target_concalls):
        date_str = c.get("date", f"Quarter {idx+1}")
        url = c.get("transcript")
        if not url:
            logger.info(f"[{symbol}] No transcript link found for {date_str}, skipping.")
            continue
            
        clean_sym = symbol.split(".")[0]
        clean_date = date_str.replace(" ", "_").replace(",", "")
        transcript_path = os.path.join(os.path.dirname(__file__), "data", "concalls", clean_sym, f"{clean_date}.txt")
        
        text = ""
        # 2a. Check if it exists locally
        if os.path.exists(transcript_path):
            logger.info(f"[{symbol}] Reading local transcript for {date_str}...")
            try:
                with open(transcript_path, "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception as e:
                logger.warning(f"[{symbol}] Could not read local file {transcript_path}: {e}")
                
        # 2b. If not local or failed to read, download it
        if not text:
            logger.info(f"[{symbol}] Downloading & extracting PDF for {date_str}...")
            try:
                text = await asyncio.to_thread(fetch_pdf_text, url)
                # Save it for next time
                try:
                    os.makedirs(os.path.dirname(transcript_path), exist_ok=True)
                    with open(transcript_path, "w", encoding="utf-8") as f:
                        f.write(text)
                except Exception as e:
                    logger.warning(f"[{symbol}] Could not save transcript backup to {transcript_path}: {e}")
            except Exception as e:
                logger.error(f"[{symbol}] Failed to extract {date_str}: {e}")
                text = f"[ERROR: Could not extract transcript for {date_str}]"
                
        combined_transcript_text += f"\n\n{'='*50}\nTRANSCRIPT FOR: {symbol} - {date_str}\n{'='*50}\n\n"
        combined_transcript_text += text
        
    # 3. Call Gemini 3.6 Flash
    logger.info(f"[{symbol}] Passing {len(combined_transcript_text)} characters to Gemini 3.6 Flash...")
    
    global current_key_idx
    
    for attempt in range(len(all_keys)):
        model = genai.GenerativeModel(
            model_name="gemini-3.6-flash",
            system_instruction=SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.2
            )
        )
        
        try:
            response = await model.generate_content_async(combined_transcript_text)
            result_json = json.loads(response.text)
            
            # Save to store
            store[symbol] = result_json
            _save_store(store)
            
            logger.info(f"[{symbol}] Successfully generated and cached longitudinal synthesis using key index {current_key_idx}!")
            return result_json
            
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "quota" in err_str or "exceeded" in err_str or "exhausted" in err_str:
                if attempt < len(all_keys) - 1:
                    current_key_idx = (current_key_idx + 1) % len(all_keys)
                    logger.warning(f"[{symbol}] Quota exceeded on key index {attempt}. Swapping to backup key index {current_key_idx} and retrying...")
                    genai.configure(api_key=all_keys[current_key_idx])
                    continue
            
            logger.error(f"[{symbol}] LLM generation failed: {e}")
            return {"error": str(e)}
            
    return {"error": "All backup Gemini API keys exhausted their quotas."}

async def sync_transcripts(symbol: str) -> Dict[str, Any]:
    """
    Checks the latest 8 quarters and downloads any missing transcripts to the local disk.
    Does NOT trigger the LLM generation.
    """
    logger.info(f"[{symbol}] Syncing transcripts...")
    all_concalls = get_concalls(symbol)
    if not all_concalls:
        return {"error": f"No concall data found for {symbol}"}
        
    target_concalls = all_concalls[:8]
    target_concalls.reverse()
    
    downloaded = 0
    already_local = 0
    
    for idx, c in enumerate(target_concalls):
        date_str = c.get("date", f"Quarter {idx+1}")
        url = c.get("transcript")
        if not url:
            continue
            
        clean_sym = symbol.split(".")[0]
        clean_date = date_str.replace(" ", "_").replace(",", "")
        transcript_path = os.path.join(os.path.dirname(__file__), "data", "concalls", clean_sym, f"{clean_date}.txt")
        
        if os.path.exists(transcript_path):
            already_local += 1
            continue
            
        logger.info(f"[{symbol}] Syncing missing PDF for {date_str}...")
        try:
            text = await asyncio.to_thread(fetch_pdf_text, url)
            os.makedirs(os.path.dirname(transcript_path), exist_ok=True)
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(text)
            downloaded += 1
        except Exception as e:
            logger.error(f"[{symbol}] Failed to download {date_str}: {e}")
            
    logger.info(f"[{symbol}] Transcript sync complete: {downloaded} downloaded, {already_local} already local.")
    return {
        "success": True,
        "downloaded": downloaded,
        "already_local": already_local,
        "message": f"Successfully synced transcripts. {downloaded} downloaded, {already_local} already local."
    }

async def ask_concalls(symbol: str, query: str) -> Dict[str, Any]:
    """
    Loads all available local transcripts for a given symbol and uses Gemini
    to answer a custom user query in rich Markdown.
    """
    logger.info(f"[{symbol}] Custom query: {query}")
    clean_sym = symbol.split(".")[0]
    concalls_dir = os.path.join(os.path.dirname(__file__), "data", "concalls", clean_sym)
    
    if not os.path.exists(concalls_dir):
        return {"error": "No transcripts found. Please sync transcripts first."}
        
    combined_transcript_text = ""
    files = sorted([f for f in os.listdir(concalls_dir) if f.endswith(".txt")])
    if not files:
        return {"error": "No transcripts found. Please sync transcripts first."}
        
    for file_name in files:
        file_path = os.path.join(concalls_dir, file_name)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            date_str = file_name.replace(".txt", "")
            combined_transcript_text += f"\n\n{'='*50}\nTRANSCRIPT FOR: {symbol} - {date_str}\n{'='*50}\n\n"
            combined_transcript_text += text
        except Exception as e:
            logger.warning(f"[{symbol}] Could not read {file_path}: {e}")
            
    if not combined_transcript_text.strip():
         return {"error": "Transcripts were empty or could not be read."}
         
    system_instruction = (
        "You are a Senior Institutional Equity Research Analyst.\n"
        "You will be given up to 8 quarters of earnings call transcripts for a company.\n"
        "Your task is to answer the user's specific query comprehensively using only the provided transcripts as evidence.\n"
        "Do NOT format your response as JSON. Instead, provide a rich, detailed, plain-English response using Markdown formatting.\n"
        "Use bullet points, bold text for emphasis, and explicitly cite the relevant quarter (e.g., 'In Q3FY24...') when making claims.\n"
        "If the transcripts do not contain the answer, say so clearly instead of guessing."
    )
    
    global current_key_idx
    for attempt in range(len(all_keys)):
        model = genai.GenerativeModel(
            model_name="gemini-3.6-flash",
            system_instruction=system_instruction,
            generation_config=genai.GenerationConfig(
                temperature=0.3
            )
        )
        try:
            prompt = f"USER QUERY: {query}\n\n{combined_transcript_text}"
            response = await model.generate_content_async(prompt)
            return {"answer": response.text}
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "quota" in err_str or "exceeded" in err_str or "exhausted" in err_str:
                if attempt < len(all_keys) - 1:
                    current_key_idx = (current_key_idx + 1) % len(all_keys)
                    logger.warning(f"[{symbol}] Quota exceeded on key index {attempt}. Swapping to backup key index {current_key_idx} and retrying...")
                    genai.configure(api_key=all_keys[current_key_idx])
                    continue
            logger.error(f"[{symbol}] LLM Q&A failed: {e}")
            return {"error": str(e)}
            
    return {"error": "All backup Gemini API keys exhausted their quotas."}

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sym = sys.argv[1] if len(sys.argv) > 1 else "INFY"
    res = asyncio.run(generate_longitudinal_synthesis(sym, force_refresh=True))
    print(json.dumps(res, indent=2))
