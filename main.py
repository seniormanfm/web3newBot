from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import joblib
import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# =============================
# 🚀 Initialize FastAPI App
# =============================
app = FastAPI(title="Crypto News & Market API", version="1.2")

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
DB_DIR = r"C:\database"
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
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        coins = response.json()
        top_coins = [
            {
                "name": coin.get("name"),
                "symbol": coin.get("symbol", "").upper(),
                "price": coin.get("current_price"),
                "change_24h": coin.get("price_change_percentage_24h"),
                "market_cap_rank": coin.get("market_cap_rank")
            }
            for coin in coins
        ]
        return {"count": len(top_coins), "coins": top_coins}
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching live data: {str(e)}")


# =============================
# 📰 CoinDesk Headlines (Saved)
# =============================
@app.get("/coindesk")
def get_coindesk_news():
    data = load_joblib("coindesk_news.joblib")
    return {
        "timestamp": data.get("timestamp"),
        "source": data.get("source"),
        "articles": data.get("articles", []),
    }


# =============================
# 🔄 Refresh Data (CoinGecko + CoinDesk)
# =============================
@app.get("/refresh")
def refresh_data():
    """Fetch new data from CoinGecko + CoinDesk and update joblib files"""

    # ----- Fetch from CoinGecko -----
    gainers_url = "https://pro-api.coingecko.com/api/v3/coins/top_gainers_losers"
    headers = {"x-cg-pro-api-key": API_KEY, "accept": "application/json"}
    params = {"vs_currency": "usd"}

    try:
        g_response = requests.get(gainers_url, headers=headers, params=params)
        g_response.raise_for_status()
        g_data = g_response.json()
        gainers_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": g_data
        }
        joblib.dump(gainers_payload, os.path.join(DB_DIR, "top_gainers_losers.joblib"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching CoinGecko data: {str(e)}")

    # ----- Fetch from CoinDesk -----
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("user-agent=Mozilla/5.0")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    url = "https://www.coindesk.com/"

    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, "h3")))
        soup = BeautifulSoup(driver.page_source, "html.parser")
        headlines = soup.find_all("h3")

        articles = []
        for headline in headlines[:30]:
            title = headline.text.strip()
            parent_link = headline.find_parent("a")
            href = parent_link["href"] if parent_link and parent_link.get("href") else None
            full_link = url + href if href and href.startswith("/") else href
            sentiment = classify_sentiment(title)
            articles.append({
                "title": title,
                "link": full_link or "No link found",
                "sentiment": sentiment
            })

        news_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "CoinDesk",
            "articles": articles
        }
        joblib.dump(news_payload, os.path.join(DB_DIR, "coindesk_news.joblib"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching CoinDesk data: {str(e)}")
    finally:
        driver.quit()

    return {
        "message": "✅ Data refreshed successfully!",
        "coingecko_updated": gainers_payload["timestamp"],
        "coindesk_updated": news_payload["timestamp"]
    }
