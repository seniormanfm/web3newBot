from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import joblib
import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from collections import Counter
import re

# =============================
# 🚀 Initialize FastAPI App
# =============================
app = FastAPI(title="Crypto News & Market API", version="2.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================
# 📁 Database Path
# =============================
DB_DIR = "/data" if os.path.exists("/data") else "database"
os.makedirs(DB_DIR, exist_ok=True)

# =============================
# 🔑 Load CoinGecko API Key
# =============================
load_dotenv()
API_KEY = os.getenv("COINGECKO_API_KEY")
if not API_KEY:
    raise ValueError("🚨 Missing COINGECKO_API_KEY in .env file!")

# =============================
# ⚙️ Helper Functions
# =============================

def load_joblib(file_name: str):
    """Safely load joblib file"""
    file_path = os.path.join(DB_DIR, file_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file_name}")
    try:
        return joblib.load(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def classify_sentiment(headline: str) -> str:
    """Simple keyword-based sentiment classifier for headlines"""
    bullish = ["surge","rally","soar","gain","bull","increase","rise","positive","record","high","jump","growth","breakout","buy","invest","pump"]
    bearish = ["drop","fall","crash","bear","decline","loss","down","negative","sell","dump","fear","panic","collapse","recession","dip"]
    text = headline.lower()
    bull_score = sum(w in text for w in bullish)
    bear_score = sum(w in text for w in bearish)
    if bull_score > bear_score:
        return "🟢 Bullish"
    elif bear_score > bull_score:
        return "🔴 Bearish"
    return "⚪ Neutral"


def summarize_text(text: str, max_sentences: int = 2) -> str:
    """Lightweight keyword-based text summarizer"""
    sentences = re.split(r'(?<=[.!?]) +', text)
    if len(sentences) <= max_sentences:
        return text

    words = re.findall(r'\w+', text.lower())
    freq = Counter(words)
    ranked = sorted(sentences, key=lambda s: sum(freq[w.lower()] for w in re.findall(r'\w+', s)), reverse=True)
    summary = " ".join(ranked[:max_sentences])
    return summary.strip()


# =============================
# 🌍 Fetch Functions
# =============================

def fetch_and_save_gainers_losers():
    """Fetch top gainers & losers from CoinGecko and save locally"""
    url = "https://pro-api.coingecko.com/api/v3/coins/top_gainers_losers"
    headers = {"x-cg-pro-api-key": API_KEY, "accept": "application/json"}
    params = {"vs_currency": "usd"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data
        }
        joblib.dump(payload, os.path.join(DB_DIR, "top_gainers_losers.joblib"))
        print("✅ Gainers/Losers data updated.")
    except Exception as e:
        print(f"⚠️ Error fetching CoinGecko data: {e}")


def fetch_and_save_coindesk_news(limit: int = 30):
    """Fetch CoinDesk news and save locally with summaries"""
    url = "https://www.coindesk.com/"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(url, headers=headers, timeout=20)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        headlines = soup.find_all("h3")

        articles = []
        for h in headlines[:limit]:
            title = h.text.strip()
            parent_link = h.find_parent("a")
            href = parent_link["href"] if parent_link and parent_link.get("href") else None
            full_link = url + href if href and href.startswith("/") else href

            sentiment = classify_sentiment(title)
            summary = summarize_text(title)

            articles.append({
                "title": title,
                "link": full_link or "No link found",
                "sentiment": sentiment,
                "summary": summary
            })

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "CoinDesk",
            "articles": articles
        }

        joblib.dump(payload, os.path.join(DB_DIR, "coindesk_news.joblib"))
        print("✅ CoinDesk news updated.")
    except Exception as e:
        print(f"⚠️ Error fetching CoinDesk news: {e}")


# =============================
# 🏠 Root Endpoint
# =============================
@app.get("/")
def home():
    return {"message": "Welcome to the Crypto News & Market API 🚀"}


# =============================
# 📈 Top Gainers & Losers (Saved)
# =============================
@app.get("/gainers-losers")
def get_gainers_losers():
    data = load_joblib("top_gainers_losers.joblib")
    return {
        "timestamp": data.get("timestamp"),
        "top_gainers": data["data"].get("top_gainers", []),
        "top_losers": data["data"].get("top_losers", []),
    }


# =============================
# 🪙 Top 100 Live Prices
# =============================
@app.get("/top-100")
def get_top_100():
    """Fetch live top 100 crypto prices from CoinGecko"""
    url = "https://pro-api.coingecko.com/api/v3/coins/markets"
    headers = {"x-cg-pro-api-key": API_KEY, "accept": "application/json"}
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": "false"
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        coins = response.json()
        return [
            {
                "name": c.get("name"),
                "symbol": c.get("symbol", "").upper(),
                "price": c.get("current_price"),
                "change_24h": c.get("price_change_percentage_24h"),
                "market_cap_rank": c.get("market_cap_rank")
            }
            for c in coins
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching live data: {e}")


# =============================
# 📰 CoinDesk Headlines (Saved)
# =============================
@app.get("/coindesk")
def get_coindesk_news():
    """Return latest CoinDesk headlines with summaries"""
    path = os.path.join(DB_DIR, "coindesk_news.joblib")
    if not os.path.exists(path):
        fetch_and_save_coindesk_news()

    data = joblib.load(path)

    # Add summaries if missing (for older files)
    for article in data.get("articles", []):
        if "summary" not in article or not article["summary"]:
            article["summary"] = summarize_text(article.get("title", ""))

    return data


# =============================
# 🔄 Refresh Endpoint
# =============================
@app.get("/refresh")
def refresh_data():
    """Manually refresh and save new data for CoinGecko + CoinDesk"""
    fetch_and_save_gainers_losers()
    fetch_and_save_coindesk_news()
    return {"message": "✅ Data refreshed successfully!"}


# =============================
# ⚡ Run on Startup
# =============================
@app.on_event("startup")
def preload_data():
    """Ensure data files exist when app starts"""
    print("🚀 App startup: Preloading data...")
    fetch_and_save_gainers_losers()
    fetch_and_save_coindesk_news()
