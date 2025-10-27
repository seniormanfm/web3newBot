import os
import asyncio
import joblib
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor

# =======================================
# 🔐 Load environment variables
# =======================================
load_dotenv()
API_KEY = os.getenv("COINGECKO_API_KEY")

# =======================================
# ⚙️ FastAPI setup
# =======================================
app = FastAPI(title="Crypto News & Market API", version="1.0")
executor = ThreadPoolExecutor(max_workers=4)

NEWS_CACHE_FILE = "coindesk_news.joblib"


# =======================================
# 🧠 Sentiment Classification
# =======================================
def classify_sentiment(headline: str) -> str:
    bullish_keywords = [
        "surge", "rally", "soar", "gain", "bull", "increase", "rise", "positive",
        "record", "high", "jump", "growth", "breakout", "buy", "invest", "pump"
    ]
    bearish_keywords = [
        "drop", "fall", "crash", "bear", "decline", "loss", "down", "negative",
        "sell", "dump", "fear", "panic", "collapse", "recession", "dip"
    ]
    text = headline.lower()
    bull_score = sum(1 for word in bullish_keywords if word in text)
    bear_score = sum(1 for word in bearish_keywords if word in text)
    if bull_score > bear_score:
        return "🟢 Bullish"
    elif bear_score > bull_score:
        return "🔴 Bearish"
    else:
        return "⚪ Neutral"


# =======================================
# 📰 CoinDesk News Scraper
# =======================================
def scrape_coindesk_news(limit=20):
    """Blocking function to scrape CoinDesk news."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/118.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get("https://www.coindesk.com/")

    try:
        WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, "h3")))
        soup = BeautifulSoup(driver.page_source, "html.parser")
        headlines = soup.find_all("h3")
    finally:
        driver.quit()

    articles = []
    for headline in headlines[:limit]:
        title = headline.text.strip()
        link = headline.find_parent("a")
        href = link["href"] if link and link.get("href") else None
        if href:
            full_link = href if href.startswith("http") else f"https://www.coindesk.com{href}"
            sentiment = classify_sentiment(title)
            articles.append({"title": title, "link": full_link, "sentiment": sentiment})

    joblib.dump(articles, NEWS_CACHE_FILE)
    return articles


async def fetch_coindesk_news(limit=20):
    """Run scraping in thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, scrape_coindesk_news, limit)


def load_cached_news():
    """Load cached news."""
    if os.path.exists(NEWS_CACHE_FILE):
        try:
            return joblib.load(NEWS_CACHE_FILE)
        except Exception:
            return []
    return []


# =======================================
# 📊 CoinGecko Data Fetchers
# =======================================
async def get_top_gainers_losers():
    if not API_KEY:
        raise HTTPException(status_code=400, detail="Missing CoinGecko API key.")

    url = "https://pro-api.coingecko.com/api/v3/coins/top_gainers_losers"
    headers = {"x-cg-pro-api-key": API_KEY, "accept": "application/json"}

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"CoinGecko error: {e}")


async def get_top_100_prices():
    if not API_KEY:
        raise HTTPException(status_code=400, detail="Missing CoinGecko API key.")

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
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"CoinGecko error: {e}")


# =======================================
# 🧩 API Routes
# =======================================

@app.get("/")
async def root():
    return {"message": "Welcome to the Crypto News & Market API 🚀"}


@app.get("/news")
async def get_news(limit: int = 20, refresh: bool = False):
    """
    Fetch or load cached CoinDesk news headlines.
    - `limit`: Number of headlines to fetch.
    - `refresh`: Set to true to force new scrape.
    """
    if refresh:
        articles = await fetch_coindesk_news(limit)
    else:
        cached = load_cached_news()
        if cached:
            articles = cached
        else:
            articles = await fetch_coindesk_news(limit)
    return JSONResponse(content={"count": len(articles), "articles": articles})


@app.get("/market/gainers-losers")
async def market_gainers_losers():
    """Fetch top gainers and losers from CoinGecko."""
    data = await get_top_gainers_losers()
    return JSONResponse(content=data)


@app.get("/market/top100")
async def market_top100():
    """Fetch top 100 crypto prices."""
    data = await get_top_100_prices()
    simplified = [{"name": c["name"], "price": c["current_price"]} for c in data]
    return JSONResponse(content={"count": len(simplified), "coins": simplified})

