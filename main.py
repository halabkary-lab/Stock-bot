import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import pandas as pd
import ta
import yfinance as yf
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("TELEGRAM_TOKEN")

# قائمة الأسهم الأكثر تداولاً ومضاربة في السوق الأمريكي
WATCHLIST = [
    "AAPL", "TSLA", "NVDA", "AMD", "AMZN", "MSFT", "META", "GOOGL",
    "PLTR", "NFLX", "COIN", "MARA", "BA", "BABA", "INTC", "MU",
    "SMCI", "ARM", "RIVN", "LCID", "SOFI", "UBER", "PYPL", "SQ",
    "DIS", "NKE", "JPM", "BAC", "V", "MA"
]

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

def analyze_stock(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        df = stock.history(period="100d")

        if df.empty or len(df) < 50:
            return None

        df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
        df['EMA20'] = ta.trend.ema_indicator(df['Close'], window=20)
        df['EMA50'] = ta.trend.ema_indicator(df['Close'], window=50)

        current_price = df['Close'].iloc[-1]
        rsi_val = df['RSI'].iloc[-1]
        ema20_val = df['EMA20'].iloc[-1]
        ema50_val = df['EMA50'].iloc[-1]

        # تصنيف الإشارة وتقييمها برقم للفرز
        score = 0
        if ema20_val > ema50_val and rsi_val < 65:
            signal = "🟢 فرصة شراء / دخول ممتازة"
            score = 3
        elif rsi_val <= 35:
            signal = "🟡 إشارة ارتداد / مناطق تجميع"
            score = 2
        elif rsi_val >= 70:
            signal = "🔴 تشبع شرائي / خروج"
            score = 0
        else:
            signal = "⚪ مسار محايد"
            score = 1

        entry_price = current_price
        target_1 = current_price * 1.03
        target_2 = current_price * 1.06
        stop_loss = current_price * 0.97

        return {
            "symbol": ticker_symbol.upper(),
            "price": current_price,
            "rsi": rsi_val,
            "ema20": ema20_val,
            "ema50": ema50_val,
            "signal": signal,
            "score": score,
            "entry": entry_price,
            "target1": target_1,
            "target2": target_2,
            "stop": stop_loss
        }
    except Exception:
        return None

def format_report(data):
    return (
        f"📊 **تقرير تحليل السهم: {data['symbol']}**\n\n"
        f"💵 **السعر الحالي:** ${data['price']:.2f}\n"
        f"📌 **التوصية:** {data['signal']}\n\n"
        f"📈 **مؤشر RSI:** {data['rsi']:.1f}\n"
        f"🔹 **EMA 20:** ${data['ema20']:.2f}\n"
        f"🔹 **EMA 50:** ${data['ema50']:.2f}\n\n"
        f"🎯 **سعر الدخول المقترح:** ${data['entry']:.2f}\n"
        f"🥇 **الهدف الأول:** ${data['target1']:.2f}\n"
        f"🥈 **الهدف الثاني:** ${data['target2']:.2f}\n"
        f"🛑 **وقف الخسارة:** ${data['stop']:.2f}\n"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "أهلاً بك! 👋\n\n"
        "🔹 أرسل **رمز أي سهم** (مثل `AAPL` أو `NVDA`) لتحليله فوراً.\n"
        "⚡ أرسل الأمر **/top** لمسح السوق واستخراج **أفضل 3 أسهم للشراء الآن**."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def scan_top_stocks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 جاري فحص قائمة أفضل الأسهم في السوق الآن... يرجى الانتظار لحضات.")
    
    results = []
    for ticker in WATCHLIST:
        data = analyze_stock(ticker)
        if data and data['score'] >= 2:  # فلترة الأسهم الممتازة فقط (شراء أو ارتداد)
            results.append(data)

    # ترتيب النتائج بناءً على قوة الإشارة
    results.sort(key=lambda x: (x['score'], -x['rsi']), reverse=True)
    top_3 = results[:3]

    if not top_3:
        await update.message.reply_text("⚪ لا توجد فرص دخول واضحة في الأسهم المراقبة حالياً. يفضل الانتظار.")
        return

    response_text = "🔥 **أفضل الفرص المتاحة للشراء/المضاربة الآن:**\n\n"
    for item in top_3:
        response_text += format_report(item) + "\n-------------------\n"

    await update.message.reply_text(response_text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    if text.startswith("/"):
        return
    
    await update.message.reply_text(f"⏳ جاري تحليل السهم {text}...")
    data = analyze_stock(text)
    if data:
        await update.message.reply_text(format_report(data), parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ لم يتم العثور على بيانات للسهم `{text}`. تأكد من الرمز.")

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("top", scan_top_stocks))
    app.add_handler(CommandHandler("scan", scan_top_stocks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.run_polling()
