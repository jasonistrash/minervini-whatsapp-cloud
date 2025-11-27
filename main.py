# main.py — Top 5 US mega-caps at ALL-TIME HIGH CLOSE (exact definition)
import os
import yfinance as yf
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
        print("Missing WhatsApp config")
        return
    url = "https://api.callmebot.com/whatsapp.php"
    params = {"phone": PHONE_NUMBER, "text": msg, "apikey": WHATSAPP_API_KEY}
    try:
        r = requests.get(url, params=params, timeout=15)
        print("Sent" if r.status_code == 200 else f"Failed: {r.text}")
    except Exception as e:
        print(f"Error: {e}")

# Top ~150 largest US stocks
TOP_TICKERS = [
    "AAPL","MSFT","NVDA","GOOGL","AMZN","META","BRK.B","TSLA","LLY","AVGO","JPM","V","WMT",
    "UNH","XOM","MA","PG","JNJ","HD","ORCL","MRK","COST","ABBV","BAC","CRM","NFLX","AMD",
    "KO","ADBE","PEP","QCOM","TMO","LIN","WFC","CSCO","MCD","INTC","ABT","DIS","VZ","AMGN",
    "PFE","CMCSA","NKE","TXN","PM","IBM","GE","HON","UNP","RTX","SPGI","CAT","NEE","GS","MS",
    "LOW","BKNG","BLK","AXP","SYK","ELV","TJX","LMT","PLD","MDT","PGR","CB","ADP","ETN","REGN"
]

def run_test():
    send_whatsapp(f"yfinance ATH CLOSE TEST — {now_hk()}")
    results = []

    for ticker in TOP_TICKERS:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5y")          # long enough for true ATH
            if len(hist) < 200:
                continue

            close = hist['Close'].iloc[-1]
            all_time_high_close = hist['Close'].max()

            # Exact definition: yesterday's close IS the highest close ever
            if close != all_time_high_close:
                continue

            info = t.info
            market_cap = info.get('marketCap') or 0
            if market_cap == 0:
                continue

            sma50  = hist['Close'].rolling(50).mean().iloc[-1]
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

    msg = f"*TOP 5 AT ALL-TIME HIGH CLOSE — {now_hk()}*\n\n"
    if not results:
        msg += "No mega-cap closed at an all-time high yesterday"
    else:
        for i, r in enumerate(results, 1):
            msg += f"*{i}. {r['ticker']}*  ${r['price']:,.2f}\n"
            msg += f"SMA50: ${r['sma50']:,.2f}  │  SMA200: ${r['sma200']:,.2f}\n"
            msg += f"Latest vol: ${r['vol_usd']:,.0f}\n"
            msg += f"10d avg vol: ${r['avg10_usd']:,.0f}\n\n"

    send_whatsapp(msg)
    send_whatsapp("Test finished")

# Flask — open URL = instant run
from flask import Flask
app = Flask(__name__)

@app.route("/")
def home():
    threading.Thread(target=run_test).start()
    return f"<h1>ATH Close Test Running… Check WhatsApp!</h1><p>{now_hk()}</p>"

if __name__ == "__main__":
    run_test()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
