import os
import sys
import datetime
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import pandas as pd
import ta
import yfinance as yf
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("TELEGRAM_TOKEN")

if not TOKEN:
    print("❌ ERROR: TELEGRAM_TOKEN variable is not set in Render environment variables!")

WATCHLIST = [
    "AAPL", "TSLA", "NVDA", "AMD", "AMZN", "MSFT", "META", "GOOGL",
    "PLTR", "NFLX", "COIN", "MARA", "BA", "BABA", "INTC", "MU",
    "SMCI", "ARM", "RIVN", "LCID", "SOFI", "UBER", "PYPL", "SQ"
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

def analyze_option_signal(ticker_symbol):
    try:
        symbol_upper = ticker_symbol.upper()
        if symbol_upper in ["SPX", "S&P500", "SP500", "SPXW"]:
            search_symbol = "^GSPC"
        else:
            search_symbol = symbol_upper

        df = yf.download(search_symbol, period="100d", interval="1d", progress=False)

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        if df.empty or len(df) < 50:
            if search_symbol == "^GSPC":
                df = yf.download("SPY", period="100d", interval="1d", progress=False)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

        if df.empty or len(df) < 50:
            return None

        df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
        df['EMA20'] = ta.trend.ema_indicator(df['Close'], window=20)
        df['EMA50'] = ta.trend.ema_indicator(df['Close'], window=50)

        current_price = float(df['Close'].iloc[-1])
        rsi_val = float(df['RSI'].iloc[-1])
        ema20_val = float(df['EMA20'].iloc[-1])
        ema50_val = float(df['EMA50'].iloc[-1])

        # 1. تحديد الاتجاه
        if ema20_val > ema50_val and 40 <= rsi_val < 70:
            option_direction = "CALL"
            option_type = "CALL 🟢 (صعود)"
            signal_desc = "اتجاه صاعد - مناسب لشراء عقود Call"
            score = 3
        elif rsi_val <= 35:
            option_direction = "CALL"
            option_type = "CALL 🟢 (ارتداد من قاع)"
            signal_desc = "مناطق تشبع بيعي - فرصة ارتداد شرائي"
            score = 2
        elif ema20_val < ema50_val or rsi_val >= 70:
            option_direction = "PUT"
            option_type = "PUT 🔴 (هبوط / تصحيح)"
            signal_desc = "اتجاه هابط أو تشبع شرائي - مناسب لعقود Put"
            score = 1
        else:
            option_direction = "NEUTRAL"
            option_type = "محايد ⚪"
            signal_desc = "تذبذب جانبي - يفضل الانتظار"
            score = 0

        # 2. حساب الـ Strike المبتعد بـ 40 نقطة (OTM)
        if search_symbol == "^GSPC":
            otm_distance = 40
            if option_direction == "CALL":
                raw_strike = current_price + otm_distance
            elif option_direction == "PUT":
                raw_strike = current_price - otm_distance
            else:
                raw_strike = current_price

            strike = round(raw_strike / 5) * 5
        else:
            strike = round(current_price / 2.5) * 2.5

        today_str = datetime.date.today().strftime("%b %d").upper()
        display_symbol = "SPX" if search_symbol == "^GSPC" else symbol_upper

        return {
            "symbol": display_symbol,
            "price": current_price,
            "rsi": rsi_val,
            "ema20": ema20_val,
            "ema50": ema50_val,
            "option_type": option_type,
            "strike": strike,
            "date": today_str,
            "signal": signal_desc,
            "score": score
        }
    except Exception as e:
        print(f"Error in analysis: {e}")
        return None

def format_option_report(data):
    opt_tag = data['option_type'].split()[0]
    return (
        f"🎯 **توصية عقد أوبشن اقتصادي OTM: {data['symbol']}**\n\n"
        f"💵 **سعر المؤشر/السهم الحالي:** ${data['price']:.2f}\n"
        f"📊 **الحالة:** {data['signal']}\n\n"
        f"🎫 **توصية العقد المقترح (بعيد عن السعر ~40 نقطة):**\n"
        f"• **النوع:** `{data['option_type']}`\n"
        f"• **سعر الإضراب (Strike):** `${data['strike']}`\n"
        f"• **التاريخ المقترح:** `{data['date']}` (0DTE / يومي)\n"
        f"• **صيغة العقد:** `({data['symbol']}) {data['date']} {data['strike']} {opt_tag}`\n\n"
        f"📈 **مؤشر RSI:** {data['rsi']:.1f}\n"
        f"🔹 **EMA 20:** ${data['ema20']:.2f} \vert{} **EMA 50:**${data['ema50']:.2f}\n"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "أهلاً بك! 👋\n\n"
        "📈 أرسل **/spx** أو كلمة **SPX** للحصول على توصية عقود **S&P 500 Options** الاقتصادية.\n"
        "⚡ أرسل **/top** لاستخراج أفضل أسهم المضاربة والعقود المتاحة."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def analyze_spx_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ جاري تحليل حركة SPX واختيار عقد أوبشن اقتصادي (OTM)...")
    data = analyze_option_signal("SPX")
    if data:
        await update.message.reply_text(format_option_report(data), parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ تعذر تحليل عقود S&P 500 حالياً.")

async def scan_top_stocks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 جاري فحص الفرص والعقود المتاحة في السوق...")
    results = []
    for ticker in WATCHLIST:
        data = analyze_option_signal(ticker)
        if data and data['score'] >= 2:
            results.append(data)

    results.sort(key=lambda x: x['score'], reverse=True)
    top_3 = results[:3]

    if not top_3:
        await update.message.reply_text("⚪ لا توجد عقود واضحة ومضمونة حالياً.")
        return

    response_text = "🔥 **أفضل عقود الأوبشن المتاحة الآن:**\n\n"
    for item in top_3:
        response_text += format_option_report(item) + "\n-------------------\n"

    await update.message.reply_text(response_text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    if text.startswith("/"):
        return
    
    if text in ["SPX", "S&P500", "SP500", "SPXW"]:
        await analyze_spx_option(update, context)
        return

    await update.message.reply_text(f"⏳ جاري تحليل عقود السهم {text}...")
    data = analyze_option_signal(text)
    if data:
        await update.message.reply_text(format_option_report(data), parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ لم يتم العثور على بيانات للسهم `{text}`. تأكد من صحة الرمز.")

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    
    if TOKEN:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("spx", analyze_spx_option))
        app.add_handler(CommandHandler("top", scan_top_stocks))
        app.add_handler(CommandHandler("scan", scan_top_stocks))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        app.run_polling()
    else:
        print("⚠️ Bot startup aborted: TELEGRAM_TOKEN missing.")
