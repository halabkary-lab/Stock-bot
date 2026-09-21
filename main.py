import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import pandas as pd
import ta
import yfinance as yf
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("TELEGRAM_TOKEN")

# سيرفر وهمي للحفاظ على تشغيل Render
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# خوارزمية تحليل السهم
def analyze_stock(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        df = stock.history(period="100d")

        if df.empty:
            return f"❌ لم يتم العثور على بيانات للسهم `{ticker_symbol}`. تأكد من الرمز."

        df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
        df['EMA20'] = ta.trend.ema_indicator(df['Close'], window=20)
        df['EMA50'] = ta.trend.ema_indicator(df['Close'], window=50)

        current_price = df['Close'].iloc[-1]
        rsi_val = df['RSI'].iloc[-1]
        ema20_val = df['EMA20'].iloc[-1]
        ema50_val = df['EMA50'].iloc[-1]

        if ema20_val > ema50_val and rsi_val < 65:
            signal = "🟢 فرصة شراء / دخول ممتازة"
            entry_price = current_price
            target_1 = current_price * 1.03
            target_2 = current_price * 1.06
            stop_loss = current_price * 0.97
        elif rsi_val <= 35:
            signal = "🟡 إشارة ارتداد / مناطق تجميع"
            entry_price = current_price
            target_1 = current_price * 1.04
            target_2 = current_price * 1.08
            stop_loss = current_price * 0.95
        elif rsi_val >= 70:
            signal = "🔴 تشبع شرائي / خروج أو تجنب الدخول"
            entry_price = current_price
            target_1 = current_price * 1.01
            target_2 = current_price * 1.02
            stop_loss = current_price * 0.98
        else:
            signal = "⚪ مسار محايد / انتظار فرصة أفضل"
            entry_price = current_price
            target_1 = current_price * 1.03
            target_2 = current_price * 1.05
            stop_loss = current_price * 0.97

        return (
            f"📊 **تقرير تحليل السهم: {ticker_symbol.upper()}**\n\n"
            f"💵 **السعر الحالي:** ${current_price:.2f}\n"
            f"📌 **التوصية:** {signal}\n\n"
            f"📈 **مؤشر RSI:** {rsi_val:.1f}\n"
            f"🔹 **EMA 20:** ${ema20_val:.2f}\n"
            f"🔹 **EMA 50:** ${ema50_val:.2f}\n\n"
            f"🎯 **سعر الدخول المقترح:** ${entry_price:.2f}\n"
            f"🥇 **الهدف الأول:** ${target_1:.2f}\n"
            f"🥈 **الهدف الثاني:** ${target_2:.2f}\n"
            f"🛑 **وقف الخسارة:** ${stop_loss:.2f}\n"
        )

    except Exception as e:
        return f"⚠️ حدث خطأ أثناء تحليل السهم: {str(e)}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "أهلاً بك! أرسل لي رمز أي سهم (مثال: AAPL أو TSLA) وسأقوم بتحليله لك فوراً."
    await update.message.reply_text(msg, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    if text.startswith("/"):
        return
    
    await update.message.reply_text(f"⏳ جاري تحليل السهم {text}...")
    result = analyze_stock(text)
    await update.message.reply_text(result, parse_mode="Markdown")

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.run_polling()
