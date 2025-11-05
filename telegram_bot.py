import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import httpx

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = "https://web3newbot.onrender.com"  # Your deployed FastAPI backend

if not BOT_TOKEN:
    raise ValueError("🚨 TELEGRAM_BOT_TOKEN not found in .env file!")

# ===============================
# 🔹 Cache Configuration
# ===============================
class SimpleCache:
    """Simple in-memory cache with expiration"""
    def __init__(self, ttl_seconds: int = 300):  # 5 minutes default
        self.cache: Dict[str, tuple[Any, datetime]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
    
    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                return data
            else:
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Any):
        self.cache[key] = (value, datetime.now())
    
    def clear(self):
        self.cache.clear()

# Initialize cache (5 minutes TTL)
cache = SimpleCache(ttl_seconds=300)

# ===============================
# 🔹 HTTP Client Configuration
# ===============================
# Reusable HTTP client with connection pooling
http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(30.0, connect=10.0),
    limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
    follow_redirects=True
)

async def fetch_with_retry(url: str, max_retries: int = 3) -> Optional[Dict]:
    """Fetch data with retry logic and exponential backoff"""
    for attempt in range(max_retries):
        try:
            logger.info(f"Fetching {url} (attempt {attempt + 1}/{max_retries})")
            response = await http_client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e}")
            if e.response.status_code >= 500 and attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            return None
        except httpx.TimeoutException:
            logger.error(f"Timeout fetching {url}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None
    return None

# ===============================
# 🔹 Commands
# ===============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message with available commands"""
    welcome_msg = (
        "👋 *Welcome to the Web3 Crypto Bot!*\n\n"
        "Available commands:\n"
        "• /news - Get latest CoinDesk news with sentiment analysis\n"
        "• /gainers - View top gainers (24h)\n"
        "• /losers - View top losers (24h)\n"
        "• /market - Get both news and market movers\n"
        "• /help - Show this help message\n\n"
        "_Data updates every 5 minutes_"
    )
    await update.message.reply_text(welcome_msg, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message"""
    await start(update, context)

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch CoinDesk news with sentiment"""
    # Check cache first
    cached_data = cache.get("news")
    if cached_data:
        logger.info("Serving news from cache")
        data = cached_data
    else:
        await update.message.reply_text("🔄 Fetching latest news...")
        data = await fetch_with_retry(f"{API_URL}/coindesk")
        
        if not data:
            await update.message.reply_text(
                "⚠️ Unable to fetch news at the moment. The server might be waking up (Render free tier). Please try again in 30 seconds."
            )
            return
        
        cache.set("news", data)
    
    try:
        if not data.get("articles"):
            await update.message.reply_text("📰 No news articles available at the moment.")
            return
        
        message = "📰 *Latest CoinDesk News*\n\n"
        for i, article in enumerate(data["articles"][:5], 1):
            title = article.get('title', 'No title')
            link = article.get('link', '')
            sentiment = article.get('sentiment', 'neutral')
            
            # Emoji for sentiment
            sentiment_emoji = {
                'positive': '🟢',
                'negative': '🔴',
                'neutral': '⚪'
            }.get(sentiment.lower(), '⚪')
            
            message += f"{i}. [{title}]({link}) {sentiment_emoji}\n\n"
        
        message += f"_Updated: {datetime.now().strftime('%H:%M:%S')}_"
        
        await update.message.reply_text(
            message, 
            parse_mode="Markdown", 
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Error formatting news: {e}")
        await update.message.reply_text(f"⚠️ Error displaying news: {str(e)}")

async def gainers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch top gainers only"""
    # Check cache first
    cached_data = cache.get("gainers")
    if cached_data:
        logger.info("Serving gainers from cache")
        data = cached_data
    else:
        await update.message.reply_text("🔄 Fetching market data...")
        data = await fetch_with_retry(f"{API_URL}/gainers-losers")
        
        if not data:
            await update.message.reply_text(
                "⚠️ Unable to fetch market data. The server might be waking up (Render free tier). Please try again in 30 seconds."
            )
            return
        
        cache.set("gainers", data)
    
    try:
        message = "📈 *Top Gainers (24h)*\n\n"
        
        if data.get("top_gainers"):
            for i, coin in enumerate(data["top_gainers"][:10], 1):
                name = coin.get('name', 'Unknown')
                symbol = coin.get('symbol', '').upper()
                change = coin.get('price_change_percentage_24h', 0)
                price = coin.get('current_price', 0)
                
                message += f"{i}. *{name}* ({symbol})\n"
                message += f"   💰 ${price:,.4f} | 📈 +{change:.2f}%\n\n"
        else:
            message += "_No data available_\n\n"
        
        message += f"_Updated: {datetime.now().strftime('%H:%M:%S')}_"
        
        await update.message.reply_text(message, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error formatting gainers: {e}")
        await update.message.reply_text(f"⚠️ Error displaying gainers: {str(e)}")

async def losers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch top losers only"""
    # Check cache first
    cached_data = cache.get("gainers")
    if cached_data:
        logger.info("Serving losers from cache")
        data = cached_data
    else:
        await update.message.reply_text("🔄 Fetching market data...")
        data = await fetch_with_retry(f"{API_URL}/gainers-losers")
        
        if not data:
            await update.message.reply_text(
                "⚠️ Unable to fetch market data. The server might be waking up (Render free tier). Please try again in 30 seconds."
            )
            return
        
        cache.set("gainers", data)
    
    try:
        message = "📉 *Top Losers (24h)*\n\n"
        
        if data.get("top_losers"):
            for i, coin in enumerate(data["top_losers"][:10], 1):
                name = coin.get('name', 'Unknown')
                symbol = coin.get('symbol', '').upper()
                change = coin.get('price_change_percentage_24h', 0)
                price = coin.get('current_price', 0)
                
                message += f"{i}. *{name}* ({symbol})\n"
                message += f"   💰 ${price:,.4f} | 📉 {change:.2f}%\n\n"
        else:
            message += "_No data available_\n\n"
        
        message += f"_Updated: {datetime.now().strftime('%H:%M:%S')}_"
        
        await update.message.reply_text(message, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error formatting losers: {e}")
        await update.message.reply_text(f"⚠️ Error displaying losers: {str(e)}")

async def market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch both news and market data in one command"""
    await update.message.reply_text("🔄 Fetching comprehensive market update...")
    
    # Fetch both endpoints concurrently
    news_task = asyncio.create_task(fetch_news_data())
    gainers_task = asyncio.create_task(fetch_gainers_data())
    
    news_data, gainers_data = await asyncio.gather(news_task, gainers_task)
    
    if not news_data and not gainers_data:
        await update.message.reply_text(
            "⚠️ Unable to fetch data. The server might be waking up. Please try again in 30 seconds."
        )
        return
    
    message = "🌐 *Complete Market Update*\n\n"
    
    # Add news section
    if news_data and news_data.get("articles"):
        message += "📰 *Latest News (Top 3):*\n"
        for i, article in enumerate(news_data["articles"][:3], 1):
            title = article.get('title', 'No title')
            link = article.get('link', '')
            sentiment = article.get('sentiment', 'neutral')
            
            sentiment_emoji = {
                'positive': '🟢',
                'negative': '🔴',
                'neutral': '⚪'
            }.get(sentiment.lower(), '⚪')
            
            message += f"{i}. [{title[:60]}...]({link}) {sentiment_emoji}\n"
        message += "\n"
    
    # Add market movers section
    if gainers_data:
        message += "📈 *Top 3 Gainers:*\n"
        if gainers_data.get("top_gainers"):
            for i, coin in enumerate(gainers_data["top_gainers"][:3], 1):
                name = coin.get('name', 'Unknown')
                symbol = coin.get('symbol', '').upper()
                change = coin.get('price_change_percentage_24h', 0)
                message += f"{i}. {name} ({symbol}): +{change:.2f}%\n"
        
        message += "\n📉 *Top 3 Losers:*\n"
        if gainers_data.get("top_losers"):
            for i, coin in enumerate(gainers_data["top_losers"][:3], 1):
                name = coin.get('name', 'Unknown')
                symbol = coin.get('symbol', '').upper()
                change = coin.get('price_change_percentage_24h', 0)
                message += f"{i}. {name} ({symbol}): {change:.2f}%\n"
    
    message += f"\n_Updated: {datetime.now().strftime('%H:%M:%S')}_"
    
    await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)

async def fetch_news_data() -> Optional[Dict]:
    """Helper function to fetch news data with caching"""
    cached_data = cache.get("news")
    if cached_data:
        return cached_data
    
    data = await fetch_with_retry(f"{API_URL}/coindesk")
    if data:
        cache.set("news", data)
    return data

async def fetch_gainers_data() -> Optional[Dict]:
    """Helper function to fetch gainers data with caching"""
    cached_data = cache.get("gainers")
    if cached_data:
        return cached_data
    
    data = await fetch_with_retry(f"{API_URL}/gainers-losers")
    if data:
        cache.set("gainers", data)
    return data

async def clear_cache_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear cache (admin command)"""
    cache.clear()
    await update.message.reply_text("✅ Cache cleared! Next requests will fetch fresh data.")

# ===============================
# 🚀 Main Function
# ===============================
async def post_init(application) -> None:
    """Initialize bot after startup"""
    logger.info("Bot initialized successfully")

async def post_shutdown(application) -> None:
    """Cleanup when shutting down"""
    await http_client.aclose()
    logger.info("HTTP client closed")

def main():
    """Start the bot"""
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("news", news))
    app.add_handler(CommandHandler("gainers", gainers))
    app.add_handler(CommandHandler("losers", losers))
    app.add_handler(CommandHandler("market", market))
    app.add_handler(CommandHandler("clear_cache", clear_cache_command))
    
    logger.info("🤖 Telegram bot is running...")
    print("🤖 Bot started successfully! Press Ctrl+C to stop.")
    
    # Run the bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise