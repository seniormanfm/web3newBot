import os
import time
import joblib
import requests
import streamlit as st
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

# =======================================
# 🔐 Load API Key
# =======================================
load_dotenv()
API_KEY = os.getenv("COINGECKO_API_KEY")

# =======================================
# 📰 Scrape Crypto News from CoinDesk
# =======================================

NEWS_CACHE_FILE = "coindesk_news.joblib"
GAINERS_CACHE_FILE = "top_gainers_losers.joblib"

def fetch_and_cache_coindesk_news(limit=20):
    """Scrape latest crypto news headlines from CoinDesk and cache results."""
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
            articles.append({"title": title, "link": full_link})
    
    joblib.dump(articles, NEWS_CACHE_FILE)
    return articles

    def classify_sentiment(headline: str) -> str:
        """Classify crypto news headline as bullish, bearish, or neutral."""
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

    def fetch_and_cache_coindesk_news(limit=10):
        """Scrape latest crypto news headlines from CoinDesk, classify sentiment, and cache to joblib file."""
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        news_url = "https://www.coindesk.com/"
        driver.get(news_url)
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


def load_coindesk_news():
    """Load cached news from disk."""
    if os.path.exists(NEWS_CACHE_FILE):
        try:
            return joblib.load(NEWS_CACHE_FILE)
        except Exception:
            return []
    return []

def load_top_gainers_losers():
    """Load cached top gainers/losers from disk."""
    if os.path.exists(GAINERS_CACHE_FILE):
        try:
            return joblib.load(GAINERS_CACHE_FILE)
        except Exception:
            return None
    return None


# =======================================
# 📊 Fetch Top Gainers/Losers from CoinGecko
# =======================================
@st.cache_data(ttl=600)
def get_top_gainers_losers():
    if not API_KEY:
        st.warning("⚠️ Missing CoinGecko API key. Add it to your .env file.")
        return None

    url = "https://pro-api.coingecko.com/api/v3/coins/top_gainers_losers"
    headers = {"x-cg-pro-api-key": API_KEY, "accept": "application/json"}
    params = {"vs_currency": "usd"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching CoinGecko data: {e}")
        return None


# =======================================
# 💹 Fetch Top 100 Crypto Prices
# =======================================
@st.cache_data(ttl=600)
def get_top_100_prices():
    if not API_KEY:
        st.warning("⚠️ Missing CoinGecko API key. Add it to your .env file.")
        return []

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
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching top 100 prices: {e}")
        return []


# =======================================
# 🖥️ Streamlit UI
# =======================================
st.set_page_config(page_title="Crypto News Blog", page_icon="🪙", layout="wide")

st.title("🪙 Crypto News & Market Movers")
st.caption("Live crypto headlines and market data powered by CoinDesk & CoinGecko")

# Sidebar: Market Movers
st.sidebar.header("📈 Market Movers")


market_data = load_top_gainers_losers()
if not market_data:
    st.sidebar.warning("No market data available in cache.")
else:
    gainers = market_data.get("top_gainers", [])[:10]
    losers = market_data.get("top_losers", [])[:10]

    col1, col2 = st.sidebar.columns(2)

    # ---- Column 1: Top Gainers ----
    with col1:
        st.subheader("🟢 Gainers")
        for coin in gainers:
            name = coin.get("name", "Unknown")
            symbol = coin.get("symbol", "").upper()
            rank = coin.get("market_cap_rank", "N/A")
            price = coin.get("usd", 0)
            change = coin.get("usd_24h_change", 0)
            volume = coin.get("usd_24h_vol", 0)
            st.markdown(f"**{name} ({symbol})**")
            st.caption(f"🏅 Rank: {rank}")
            st.metric("💵 Price", f"${price:,.2f}", f"{change:.2f}%")
            st.caption(f"📊 Vol: ${volume:,.0f}")
            st.markdown("---")

    # ---- Column 2: Top Losers ----
    with col2:
        st.subheader("🔴 Losers")
        for coin in losers:
            name = coin.get("name", "Unknown")
            symbol = coin.get("symbol", "").upper()
            rank = coin.get("market_cap_rank", "N/A")
            price = coin.get("usd", 0)
            change = coin.get("usd_24h_change", 0)
            volume = coin.get("usd_24h_vol", 0)
            st.markdown(f"**{name} ({symbol})**")
            st.caption(f"🏅 Rank: {rank}")
            st.metric("💵 Price", f"${price:,.2f}", f"{change:.2f}%")
            st.caption(f"📊 Vol: ${volume:,.0f}")
            st.markdown("---")


# =======================================
# 📰 Main Section: News
# =======================================
refresh = st.button("🔄 Refresh CoinDesk News", help="Fetch the latest crypto headlines")

if refresh:
    with st.spinner("Fetching latest crypto news..."):
        news = fetch_and_cache_coindesk_news(limit=20)
else:
    news = load_coindesk_news()

st.markdown("## 🗞 Latest Crypto News")
if not news:
    st.info("No crypto news found. Click 'Refresh CoinDesk News' to fetch.")
else:
    for item in news:
            st.subheader(item["title"])
            st.write(f"Sentiment: {item.get('sentiment', 'N/A')}")
            st.markdown(f"[Read full article →]({item['link']})")
            st.markdown("---")


# =======================================
# 💰 Top 100 Prices
# =======================================
st.markdown("## 💰 Top 100 Crypto Prices (USD)")
top100 = get_top_100_prices()

if not top100:
    st.info("No price data available.")
else:
    for coin in top100:
        name = coin.get("name", "Unknown")
        price = coin.get("current_price", "N/A")
        st.write(f"**{name}** — ${price:,.2f}")

st.markdown("📰 **Data sources:** CoinDesk & CoinGecko | Built with ❤️ using Streamlit")
