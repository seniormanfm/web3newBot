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
API_URL = "https://web3newbot.onrender.com"

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

cache = SimpleCache(ttl_seconds=300)

# ===============================
# 🔹 HTTP Client
# ===============================
http_client = httpx.AsyncClient(timeout=30.0)


async def fetch_data(endpoint: str) -> Optional[Dict]:
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
        "• /news - Latest CoinDesk news (20 headlines)\n"
        "• /gainers - Top 20 gainers (24h)\n"
        "• /losers - Top 20 losers (24h)\n"
        "• /market - Combined 24h overview\n"
        "• /help - Show this message\n\n"
        "_Data is fetched live on demand._"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# ================================
# NEWS – FIXED TO SHOW TOP 20
# ================================
async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Fetching latest news...")
    data = await fetch_data("coindesk")

    if not data or not data.get("articles"):
        await update.message.reply_text("⚠️ No news available right now.")
        return

    message = "📰 *Latest CoinDesk News*\n\n"
    for i, article in enumerate(data["articles"][:20], 1):
        title = article.get("title", "No title")
        link = article.get("link", "")
        sentiment = article.get("sentiment", "neutral").lower()

        emoji = {
            "positive": "🟢",
            "negative": "🔴",
            "neutral": "⚪"
        }.get(sentiment, "⚪")

        message += f"{i}. [{title}]({link}) {emoji}\n\n"

    message += f"_Updated: {datetime.now().strftime('%H:%M:%S')}_"
    await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)

# ================================
# GAINERS – FIXED FIELDS
# ================================
async def gainers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Fetching top gainers...")
    data = await fetch_data("gainers-losers")

    if not data or not data.get("top_gainers"):
        await update.message.reply_text("⚠️ No market data available.")
        return

    message = "📈 *Top 20 Gainers (24h)*\n\n"
    for i, coin in enumerate(data["top_gainers"][:20], 1):
        name = coin.get("name")
        symbol = coin.get("symbol", "").upper()
        price = coin.get("usd", 0)
        change = coin.get("usd_24h_change", 0)
        volume = coin.get("usd_24h_vol", 0)

        message += (
            f"{i}. *{name}* ({symbol})\n"
            f"   💰 Price: `${price:,.6f}`\n"
            f"   📈 24h Change: `{change:.2f}%`\n"
            f"   🔊 Volume: `${volume:,.0f}`\n\n"
        )

    message += f"_Updated: {datetime.now().strftime('%H:%M:%S')}_"
    await update.message.reply_text(message, parse_mode="Markdown")

# ================================
# LOSERS – FIXED FIELDS
# ================================
async def losers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Fetching top losers...")
    data = await fetch_data("gainers-losers")

    if not data or not data.get("top_losers"):
        await update.message.reply_text("⚠️ No market data available.")
        return

    message = "📉 *Top 20 Losers (24h)*\n\n"
    for i, coin in enumerate(data["top_losers"][:20], 1):
        name = coin.get("name")
        symbol = coin.get("symbol", "").upper()
        price = coin.get("usd", 0)
        change = coin.get("usd_24h_change", 0)
        volume = coin.get("usd_24h_vol", 0)

        message += (
            f"{i}. *{name}* ({symbol})\n"
            f"   💰 Price: `${price:,.6f}`\n"
            f"   📉 24h Change: `{change:.2f}%`\n"
            f"   🔊 Volume: `${volume:,.0f}`\n\n"
        )

    message += f"_Updated: {datetime.now().strftime('%H:%M:%S')}_"
    await update.message.reply_text(message, parse_mode="Markdown")

# ================================
# MARKET OVERVIEW
# ================================
async def market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Fetching market update...")

    news_data, market_data = await asyncio.gather(
        fetch_data("coindesk"),
        fetch_data("gainers-losers")
    )

    if not news_data and not market_data:
        await update.message.reply_text("⚠️ Unable to fetch data.")
        return

    message = "🌐 *Market Overview (24h)*\n\n"

    # Top news
    if news_data and news_data.get("articles"):
        message += "📰 *Top News:*\n"
        for i, article in enumerate(news_data["articles"][:3], 1):
            title = article.get("title", "No title")
            link = article.get("link", "")
            message += f"{i}. [{title[:60]}...]({link})\n"
        message += "\n"

    # Top gainers
    if market_data:
        message += "📈 *Top Gainers:*\n"
        for i, coin in enumerate(market_data.get("top_gainers", [])[:3], 1):
            name = coin["name"]
            symbol = coin["symbol"].upper()
            change = coin["usd_24h_change"]
            message += f"{i}. {name} ({symbol}): +{change:.2f}%\n"

        message += "\n📉 *Top Losers:*\n"
        for i, coin in enumerate(market_data.get("top_losers", [])[:3], 1):
            name = coin["name"]
            symbol = coin["symbol"].upper()
            change = coin["usd_24h_change"]
            message += f"{i}. {name} ({symbol}): {change:.2f}%\n"

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
