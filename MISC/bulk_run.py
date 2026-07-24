import asyncio
import logging
from dotenv import load_dotenv
import os

load_dotenv(r'E:\Website\Stock Analysis\stock ticker v2\backend\.env')

# Need to append backend path so it can find extra_service
import sys
sys.path.append(r'E:\Website\Stock Analysis\stock ticker v2\backend')

from concall_factor_service import bulk_refresh

logging.basicConfig(level=logging.INFO, format="%(message)s")

async def main():
    symbols = ["TCS", "HDFCBANK", "WIPRO", "HCLTECH"]
    print(f"Starting bulk refresh for: {symbols}")
    print("This will take approximately 8-10 minutes due to the 15 RPM rate limit.")
    results = await bulk_refresh(symbols)
    print("\nBulk refresh completed!")
    print(results)

if __name__ == "__main__":
    asyncio.run(main())
