import os
import time
import joblib
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv
import streamlit as st

# =======================================
# 🔐 Load API Key
# =======================================
load_dotenv()
API_KEY = os.getenv("COINGECKO_API_KEY")

# =======================================
# 📰 Scrape Crypto News from CoinDesk
# =======================================

NEWS_CACHE_FILE = "coindesk_news.joblib"

def fetch_and_cache_coindesk_news(limit=20):
    """Scrape latest crypto news headlines from CoinDesk and cache to joblib file."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/118.0.0.0 Safari/537.36")
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
            articles.append({"title": title, "link": full_link})
    joblib.dump(articles, NEWS_CACHE_FILE)
    return articles

def load_coindesk_news():
    if os.path.exists(NEWS_CACHE_FILE):
        try:
            return joblib.load(NEWS_CACHE_FILE)
        except Exception:
            return []
    return []


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
# 🖥️ Streamlit UI
# =======================================
st.set_page_config(page_title="Crypto News Blog", page_icon="🪙", layout="wide")
st.title("🪙 Crypto News & Market Movers")
st.caption("Live crypto headlines and price movers powered by CoinDesk and CoinGecko")

# Sidebar: show top gainers/losers
st.sidebar.header("📈 Market Movers")

st.sidebar.header("📊 Market Movers")

market_data = get_top_gainers_losers()

if not market_data:
    st.sidebar.warning("No market data available.")
else:
    gainers = market_data.get("top_gainers", [])[:10]
    losers = market_data.get("top_losers", [])[:10]

    # Create two side-by-side columns inside the sidebar
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

            st.markdown(f"**{name}** ({symbol})")
            st.caption(f"🏅 Rank: {rank}")
            st.metric(
                label="💵 Price (USD)",
                value=f"${price:,.2f}",
                delta=f"{change:.2f}%",
                delta_color="normal"
            )
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

            st.markdown(f"**{name}** ({symbol})")
            st.caption(f"🏅 Rank: {rank}")
            st.metric(
                label="💵 Price (USD)",
                value=f"${price:,.2f}",
                delta=f"{change:.2f}%",
                delta_color="inverse"
            )
            st.caption(f"📊 Vol: ${volume:,.0f}")
            st.markdown("---")



# Main blog content
refresh = st.button("🔄 Refresh News from CoinDesk", help="Fetch latest news and update cache")
if refresh:
    with st.spinner("Fetching latest crypto news from CoinDesk..."):
        news = fetch_and_cache_coindesk_news(limit=10)
else:
    news = load_coindesk_news()

if not news:
    st.error("No crypto news found. Click 'Refresh News from CoinDesk' to fetch.")
else:
    for item in news:
        st.subheader(item["title"])
        st.markdown(f"[Read full article →]({item['link']})")
        st.markdown("---")

# Footer
st.markdown("📰 **Data sources:** CoinDesk & CoinGecko | Built with ❤️ using Streamlit")
