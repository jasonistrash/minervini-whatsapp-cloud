# main.py — Top 5 US stocks at ATH + SMA + Volume in USD (Test yfinance data)
import os
import yfinance as yf
import pandas as pd
import requests
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

hk_tz = ZoneInfo("Asia/Hong_Kong")
def now_hk():
    return datetime.now(hk_tz).strftime("%d %b %Y %H:%M HK")

WHATSAPP_API_KEY = os.getenv('WHATSAPP_API_KEY')
PHONE_NUMBER     = os.getenv('PHONE_NUMBER')

def send_whatsapp(msg):
    if not WHATSAPP_API_KEY or not PHONE_NUMBER:
        print("WhatsApp config missing")
        return
    url = "https://api.callmebot.com/whatsapp.php"
    params = {"phone": PHONE_NUMBER, "text": msg, "apikey": WHATSAPP_API_KEY}
    try:
        r = requests.get(url, params=params, timeout=15)
        print("WhatsApp sent" if r.status_code == 200 else f"Failed: {r.text}")
    except Exception as e:
        print(f"WhatsApp error: {e}")

TOP_TICKERS = [
    "AAPL","MSFT","NVDA","GOOGL","AMZN","META","BRK.B","TSLA","LLY","AVGO",
    "JPM","V","WMT","UNH","XOM","MA","PG","JNJ","HD","ORCL","MRK","COST","ABBV","BAC","CRM",
    "NFLX","AMD","KO","ADBE","PEP","QCOM","TMO","LIN","WFC","CSCO","MCD","INTC","ABT","DIS",
    "VZ","AMGN","PFE","CMCSA","NKE","TXN","PM","IBM","GE","HON","UNP","RTX","SPGI","CAT",
    "NEE","GS","MS","LOW","BKNG","BLK","AXP","SYK","ELV","TJX","LMT","PLD","MDT","PGR","CB"
]

def run_test():
    send_whatsapp(f"yfinance ATH TEST STARTED — {now_hk()}")
    results = []

    for ticker in TOP_TICKERS:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="2y")
            if len(hist) < 250:
                continue

            close = hist['Close'].iloc[-1]
            prev_ath = hist['High'][:-1].max()
            if close < prev_ath:
                continue

            market_cap = t.info.get('marketCap') or 0
            if market_cap == 0:
                continue

            sma50 = hist['Close'].rolling(50).mean().iloc[-1]
            sma200 = hist['Close'].rolling(200).mean().iloc[-1]
            latest_vol_usd = hist['Volume'].iloc[-1] * close
            avg_vol_10d_usd = (hist['Volume'].tail(10) * hist['Close'].tail(10)).mean()

            results.append({
                'ticker': ticker,
                'price': close,
                'sma50': sma50,
                'sma200': sma200,
                'vol_usd': latest_vol_usd,
                'avg10_usd': avg_vol_10d_usd,
                'mcap': market_cap
            })
        except:
            continue

    results = sorted(results, key=lambda x: x['mcap'], reverse=True)[:5]

    msg = f"*TOP 5 ATH STOCKS — {now_hk()}*\n\n"
    if not results:
        msg += "No stock closed at all-time high today"
    else:
        for i, r in enumerate(results, 1):
            msg += f"*{i}. {r['ticker']}*  ${r['price']:,.2f}\n"
            msg += f"SMA50: ${r['sma50']:,.2f}  │  SMA200: ${r['sma200']:,.2f}\n"
            msg += f"Latest vol: ${r['vol_usd']:,.0f}\n"
            msg += f"10d avg vol: ${r['avg10_usd']:,.0f}\n\n"

    send_whatsapp(msg)
    send_whatsapp("ATH test complete")

# Flask so you can trigger instantly
from flask import Flask
app = Flask(__name__)

@app.route("/")
def home():
    threading.Thread(target=run_test).start()
    return f"<h1>ATH Test Running… Check WhatsApp!</h1><p>{now_hk()}</p>"

if __name__ == "__main__":
    run_test()  # runs once on deploy
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
