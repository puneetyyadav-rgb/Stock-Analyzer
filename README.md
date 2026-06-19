# Stock Analyzer

A sophisticated, full-stack stock analysis dashboard explicitly tailored for Indian Equities (NSE/BSE). This tool aggregates fundamental data, technical indicators, AI-driven insights, and live exchange data into a sleek, Bloomberg-terminal-esque React interface.

## 🚀 Key Features

- **9-Factor AI Framework**: Analyzes stocks based on a deep 9-factor model (Macro, Micro, Industry, Policy, News, Financials, etc.).
- **Live Market Depth & Options Chain**: Direct integration with the **Kotak Neo API** to pull real-time Level 2 Market Depth and authentic NSE Futures & Options chains (with live Put-Call Ratio calculation).
- **Institutional Flows**: Tracks Foreign Institutional Investor (FII) and Domestic Institutional Investor (DII) data.
- **Financials & Corporate Actions**: Fetches dividends, stock splits, historical data, and peer comparison data.
- **Premium UI**: Built with React and TailwindCSS featuring a dynamic dark-mode interface designed for power users.

## 🛠️ Technology Stack

- **Frontend**: React.js, TailwindCSS, Axios
- **Backend**: Python, FastAPI, Uvicorn
- **Integrations**: Kotak Neo API V2, yfinance, Google Generative AI (Gemini)
- **Database/Cache**: MongoDB (optional/configurable), In-memory caching

## ⚙️ Setup & Installation

### 1. Backend Configuration
Navigate to the `backend/` directory and install the Python dependencies:
```bash
cd backend
pip install -r requirements.txt
```

Create a `.env` file in the `backend/` directory and provide your API keys:
```env
# Kotak Neo API Credentials (For Live Options & Depth)
KOTAK_CONSUMER_KEY="your_consumer_key"
KOTAK_CONSUMER_SECRET="your_consumer_secret"
KOTAK_MOBILE_NUM="+91XXXXXXXXXX"
KOTAK_MPIN="XXXX"
KOTAK_UCC="YOUR_UCC_ID"
KOTAK_TOTP_SECRET="your_totp_secret_key"
KOTAK_PASSWORD="your_password"

# AI Credentials
GEMINI_API_KEY="your_google_gemini_key"
```

Start the FastAPI server:
```bash
python -m uvicorn server:app --reload
```
The backend will run on `http://127.0.0.1:8000`.

### 2. Frontend Configuration
Navigate to the `frontend/` directory and install the Node.js dependencies:
```bash
cd frontend
npm install
```

Start the React development server:
```bash
npm start
```
The frontend will run on `http://localhost:3000` (or 3001 depending on availability).

## 🔒 Security Note
Do not commit your `.env` file! The `.gitignore` is pre-configured to ignore all `*.env` files to protect your Kotak Neo trading credentials and AI keys.

## 🤝 Contributing
Feel free to open issues or submit pull requests for new feature integrations.
