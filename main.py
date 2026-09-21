import os
import logging
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update

logging.basicConfig(level=logging.INFO)

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك! البوت يعمل بنجاح. أرسل /scan لبدء تحليل الأسهم.")

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("جاري فحص وتراقب الأسهم... سينتهي التحليل ويصلك التقرير خلال لحظات.")

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN environment variable is missing!")
        
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan))
    
    logging.info("Starting Telegram Bot...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
