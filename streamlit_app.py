import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time

st.set_page_config(page_title="Crypto News Blog", layout="wide")
st.title("📰 Latest Crypto News from CoinDesk")

# Set up Selenium with headless Chrome
options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

try:
    url = "https://www.coindesk.com/"
    st.info("Fetching news from CoinDesk...")
    driver.get(url)
    WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.TAG_NAME, "h3"))
    )
    soup = BeautifulSoup(driver.page_source, "html.parser")
    headlines = soup.find_all("h3")
    st.write(f"Found {len(headlines)} headlines.")
    if not headlines:
        st.warning("No headlines found. The page structure may have changed.")
        st.text(soup.prettify()[:1000])
    else:
        for i, headline in enumerate(headlines[:5], 1):
            try:
                title = headline.text.strip()
                parent_link = headline.find_parent("a")
                link = parent_link["href"] if parent_link and parent_link.get("href") else "#"
                full_link = url + link if link.startswith("/") else link
                st.markdown(f"### {i}. [{title}]({full_link})")
            except Exception as e:
                st.error(f"Error processing headline {i}: {str(e)}")
except Exception as e:
    st.error(f"An error occurred: {str(e)}")
finally:
    driver.quit()