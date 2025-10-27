import os
import joblib
import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

# -------------------------------
# ⚙️ Setup
# -------------------------------
load_dotenv()
SAVE_DIR = r"C:\database"
os.makedirs(SAVE_DIR, exist_ok=True)

API_KEY = os.getenv("COINGECKO_API_KEY")
if not API_KEY:
    raise ValueError("🚨 Missing API key! Set COINGECKO_API_KEY in your .env file.")

# -------------------------------
# 🧠 Sentiment Classifier
# -------------------------------
def classify_sentiment(headline: str) -> str:
    bullish = ["surge","rally","soar","gain","bull","increase","rise","positive",
               "record","high","jump","growth","breakout","buy","invest","pump"]
    bearish = ["drop","fall","crash","bear","decline","loss","down","negative",
               "sell","dump","fear","panic","collapse","recession","dip"]

    text = headline.lower()
    bull_score = sum(w in text for w in bullish)
    bear_score = sum(w in text for w in bearish)
    if bull_score > bear_score:
        return "🟢 Bullish"
    elif bear_score > bull_score:
        return "🔴 Bearish"
    return "⚪ Neutral"


# -------------------------------
# 🌐 CoinGecko API Helpers
# -------------------------------
def fetch_top_gainers_losers():
    """Fetch top gainers & losers from CoinGecko Pro API and save locally."""
    url = "https://pro-api.coingecko.com/api/v3/coins/top_gainers_losers"
    headers = {"x-cg-pro-api-key": API_KEY, "accept": "application/json"}
    params = {"vs_currency": "usd"}

    response = requests.get(url, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data
    }

    save_path = os.path.join(SAVE_DIR, "top_gainers_losers.joblib")
    joblib.dump(payload, save_path)
    print(f"✅ Saved top gainers/losers to {save_path}")
    return payload


def fetch_top_100_coins():
    """Fetch top 100 coins by market cap (CoinGecko Pro API)."""
    url = "https://pro-api.coingecko.com/api/v3/coins/markets"
    headers = {"x-cg-pro-api-key": API_KEY, "accept": "application/json"}
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": "false"
    }

    response = requests.get(url, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data
    }

    save_path = os.path.join(SAVE_DIR, "top_100_coins.joblib")
    joblib.dump(payload, save_path)
    print(f"✅ Saved top 100 coins to {save_path}")
    return payload


# -------------------------------
# 📰 CoinDesk Headlines
# -------------------------------
def fetch_and_save_coindesk_news(limit: int = 30):
    """Scrape CoinDesk homepage headlines and classify sentiment."""
    save_file = os.path.join(SAVE_DIR, "coindesk_news.joblib")

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    url = "https://www.coindesk.com/"

    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, "h3")))
        soup = BeautifulSoup(driver.page_source, "html.parser")
        headlines = soup.find_all("h3")

        articles = []
        for headline in headlines[:limit]:
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

        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "CoinDesk",
            "articles": articles
        }

        joblib.dump(data, save_file)
        print(f"✅ Saved {len(articles)} CoinDesk articles to {save_file}")
        return data

    except Exception as e:
        print(f"❌ Error fetching CoinDesk news: {e}")
        return None
    finally:
        driver.quit()


# -------------------------------
# 🧾 Loader Helpers
# -------------------------------
def load_saved_data(filename: str):
    """Load any saved .joblib file from C:\database"""
    path = os.path.join(SAVE_DIR, filename)
    if not os.path.exists(path):
        print(f"⚠️ File not found: {path}")
        return None
    return joblib.load(path)


# -------------------------------
# ▶️ Run manually for testing
# -------------------------------
if __name__ == "__main__":
    print("\n🚀 Fetching crypto data...")
    fetch_top_gainers_losers()
    fetch_top_100_coins()
    fetch_and_save_coindesk_news()
    print("\n✅ All data sources updated successfully.")
