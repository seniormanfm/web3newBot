import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
from transformers import pipeline

# --- Setup summarizer (uses a small, fast transformer model) ---
@st.cache_resource
def load_summarizer():
    return pipeline("summarization", model="facebook/bart-large-cnn")

summarizer = load_summarizer()

# --- Function to scrape headlines ---
@st.cache_data(ttl=3600)
def scrape_news():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    url = "https://www.coindesk.com/"
    driver.get(url)
    time.sleep(5)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    articles_data = []
    for article in soup.find_all("div", class_="nws-article"):
        title_tag = article.find("h3", class_="nws-article__headline")
        link_tag = article.find("a")
        if title_tag and link_tag:
            title = title_tag.text.strip()
            link = link_tag["href"]
            articles_data.append({"title": title, "link": link})

    return articles_data

# --- Streamlit UI ---
st.set_page_config(page_title="Crypto News Blog", page_icon="🪙", layout="wide")
st.title("🪙 Crypto News Blog")
st.caption("Live crypto headlines from NewsNow, summarized for you automatically!")

if st.button("🔄 Refresh News"):
    st.cache_data.clear()

with st.spinner("Fetching latest crypto news..."):
    articles = scrape_news()

if not articles:
    st.error("No news articles found. Try refreshing.")
else:
    for i, article in enumerate(articles[:10]):  # limit to 10 articles
        st.subheader(article["title"])
        st.markdown(f"[Read Original]({article['link']})")

        # Summarize the headline (and optionally article snippet)
        try:
            summary = summarizer(article["title"], max_length=30, min_length=10, do_sample=False)[0]["summary_text"]
            st.write("📝 Summary:", summary)
        except Exception as e:
            st.warning(f"Couldn't summarize: {e}")

        st.markdown("---")
