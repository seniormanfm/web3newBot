import os
import asyncio
import httpx  # Use httpx instead of requests for async
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = "http://127.0.0.1:8000"  # Your FastAPI backend

if not BOT_TOKEN:
    raise ValueError("🚨 TELEGRAM_BOT_TOKEN not found in .env file!")

# ===============================
# 🔹 Commands
# ===============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome to the Crypto Bot! Use /news or /gainers to get updates.")

async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch CoinDesk news with sentiment"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(f"{API_URL}/coindesk")
            res.raise_for_status()
            data = res.json()

        message = "📰 *Latest CoinDesk News*\n\n"
        for a in data["articles"][:5]:
            message += f"• [{a['title']}]({a['link']}) — {a['sentiment']}\n"

        await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error fetching news: {e}")

async def gainers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch top gainers and losers"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(f"{API_URL}/gainers-losers")
            res.raise_for_status()
            data = res.json()

        message = "📈 *Top Gainers:*\n"
        for g in data["top_gainers"][:5]:
            message += f"• {g['name']} ({g['symbol'].upper()}): +{g['price_change_percentage_24h']:.2f}%\n"

        message += "\n📉 *Top Losers:*\n"
        for l in data["top_losers"][:5]:
            message += f"• {l['name']} ({l['symbol'].upper()}): {l['price_change_percentage_24h']:.2f}%\n"

        await update.message.reply_text(message, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error fetching gainers/losers: {e}")

# ===============================
# 🚀 Main Function
# ===============================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news))
    app.add_handler(CommandHandler("gainers", gainers))
    print("🤖 Telegram bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()