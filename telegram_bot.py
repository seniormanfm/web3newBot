import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import httpx

# ===============================
# 🔹 Logging setup
# ===============================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===============================
# 🔹 Environment setup
# ===============================
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = "https://web3newbot.onrender.com"  # your backend endpoint

if not BOT_TOKEN:
    raise ValueError("🚨 TELEGRAM_BOT_TOKEN not found in .env file!")

# ===============================
# 🔹 Simple cache (optional)
# ===============================
class SimpleCache:
    def __init__(self, ttl_seconds: int = 300):
        self.cache: Dict[str, tuple[Any, datetime]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)

    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                return data
            del self.cache[key]
        return None

    def set(self, key: str, value: Any):
        self.cache[key] = (value, datetime.now())

    def clear(self):
        self.cache.clear()

cache = SimpleCache(ttl_seconds=300)

# ===============================
# 🔹 HTTP Client
# ===============================
http_client = httpx.AsyncClient(timeout=30.0)

async def fetch_data(endpoint: str) -> Optional[Dict]:
    """Fetch data from backend only when user requests it"""
    url = f"{API_URL}/{endpoint}"
    try:
        logger.info(f"Fetching data from {url}")
        response = await http_client.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return None

# ===============================
# 🔹 Telegram Commands
# ===============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 *Welcome to the Web3 Crypto Bot!*\n\n"
        "Available commands:\n"
        "• /news - Latest CoinDesk news\n"
        "• /gainers - Top gainers (24h)\n"
        "• /losers - Top losers (24h)\n"
        "• /market - Combined news and market overview\n"
        "• /help - Show this message\n\n"
        "_Data is fetched only when you request it._"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Fetching latest news...")
    data = await fetch_data("coindesk")

    if not data or not data.get("articles"):
        await update.message.reply_text("⚠️ No news available right now.")
        return

    message = "📰 *Latest CoinDesk News*\n\n"
    for i, article in enumerate(data["articles"][:5], 1):
        title = article.get("title", "No title")
        link = article.get("link", "")
        sentiment = article.get("sentiment", "neutral")
        emoji = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}.get(sentiment.lower(), "⚪")
        message += f"{i}. [{title}]({link}) {emoji}\n\n"
    message += f"_Updated: {datetime.now().strftime('%H:%M:%S')}_"

    await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)

async def gainers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Fetching top gainers...")
    data = await fetch_data("gainers-losers")

    if not data or not data.get("top_gainers"):
        await update.message.reply_text("⚠️ No market data available.")
        return

    message = "📈 *Top Gainers (24h)*\n\n"
    for i, coin in enumerate(data["top_gainers"][:10], 1):
        name = coin.get("name", "Unknown")
        symbol = coin.get("symbol", "").upper()
        change = coin.get("price_change_percentage_24h", 0)
        price = coin.get("current_price", 0)
        message += f"{i}. *{name}* ({symbol})\n   💰 ${price:,.4f} | 📈 +{change:.2f}%\n\n"
    message += f"_Updated: {datetime.now().strftime('%H:%M:%S')}_"

    await update.message.reply_text(message, parse_mode="Markdown")

async def losers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Fetching top losers...")
    data = await fetch_data("gainers-losers")

    if not data or not data.get("top_losers"):
        await update.message.reply_text("⚠️ No market data available.")
        return

    message = "📉 *Top Losers (24h)*\n\n"
    for i, coin in enumerate(data["top_losers"][:10], 1):
        name = coin.get("name", "Unknown")
        symbol = coin.get("symbol", "").upper()
        change = coin.get("price_change_percentage_24h", 0)
        price = coin.get("current_price", 0)
        message += f"{i}. *{name}* ({symbol})\n   💰 ${price:,.4f} | 📉 {change:.2f}%\n\n"
    message += f"_Updated: {datetime.now().strftime('%H:%M:%S')}_"

    await update.message.reply_text(message, parse_mode="Markdown")

async def market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Fetching market update...")
    news_data, market_data = await asyncio.gather(
        fetch_data("coindesk"), fetch_data("gainers-losers")
    )

    if not news_data and not market_data:
        await update.message.reply_text("⚠️ Unable to fetch data.")
        return

    message = "🌐 *Market Overview*\n\n"

    if news_data and news_data.get("articles"):
        message += "📰 *Top News:*\n"
        for i, article in enumerate(news_data["articles"][:3], 1):
            title = article.get("title", "No title")
            link = article.get("link", "")
            message += f"{i}. [{title[:60]}...]({link})\n"
        message += "\n"

    if market_data:
        message += "📈 *Top Gainers:*\n"
        for i, coin in enumerate(market_data.get("top_gainers", [])[:3], 1):
            message += f"{i}. {coin.get('name', 'Unknown')} ({coin.get('symbol', '').upper()}): +{coin.get('price_change_percentage_24h', 0):.2f}%\n"

        message += "\n📉 *Top Losers:*\n"
        for i, coin in enumerate(market_data.get("top_losers", [])[:3], 1):
            message += f"{i}. {coin.get('name', 'Unknown')} ({coin.get('symbol', '').upper()}): {coin.get('price_change_percentage_24h', 0):.2f}%\n"

    message += f"\n_Updated: {datetime.now().strftime('%H:%M:%S')}_"
    await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)

# ===============================
# 🚀 Main entry
# ===============================
async def post_shutdown(application):
    await http_client.aclose()

def main():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("news", news))
    app.add_handler(CommandHandler("gainers", gainers))
    app.add_handler(CommandHandler("losers", losers))
    app.add_handler(CommandHandler("market", market))

    logger.info("🤖 Bot started and waiting for user commands...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
