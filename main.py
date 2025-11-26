# main.py — FINAL CLEAN VERSION (US + HK, no VCP, no syntax errors)
import os
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime
import time
import math
import threading
from zoneinfo import ZoneInfo

hk_tz = ZoneInfo("Asia/Hong_Kong")
def now_hk():
    return datetime.now(hk_tz).strftime("%d %b %Y %H:%M HK")

# ==================== CONFIG ====================
WHATSAPP_API_KEY = os.getenv('WHATSAPP_API_KEY')
PHONE_NUMBER     = os.getenv('PHONE_NUMBER')
HKD_PORTFOLIO    = float(os.getenv('HKD_PORTFOLIO', '3300000'))
RISK_HKD         = HKD_PORTFOLIO * 0.005
# ===============================================

def send_whatsapp(msg):
    if not WHATSAPP_API_KEY or not PHONE_NUMBER:
        print("Missing WhatsApp config")
        return
    url = "https://api.callmebot.com/whatsapp.php"
    params = {"phone": PHONE_NUMBER, "text": msg, "apikey": WHATSAPP_API_KEY}
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            print("WhatsApp sent")
        else:
            print(f"WhatsApp error: {r.text}")
    except Exception as e:
        print(f"WhatsApp failed: {e}")

# === TICKERS ===
def get_hk_tickers():
    try:
        url = "https://raw.githubusercontent.com/rreichel3/HK-Stock-Symbols/main/hk_stock_symbols.csv"
        df = pd.read_csv(url)
        return [f"{row.Symbol}.HK" for row in df.itertuples() if str(row.Symbol).isdigit()]
    except:
        return ['0700.HK','9988.HK','3690.HK','9618.HK','1211.HK','1810.HK','9888.HK']

def get_all_tickers():
    us = []
    try:
        nasdaq = pd.read_csv("https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/us_stock_symbols/nasdaq_full_tickers.csv")['Symbol'].tolist()
        nyse   = pd.read_csv("https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/us_stock_symbols/nyse_full_tickers.csv")['Symbol'].tolist()
        us = [t for t in nasdaq + nyse if isinstance(t, str) and t.strip()]
    except:
        pass
    return us + get_hk_tickers()

# === HELPERS ===
def volume_bias_ok(df):
    recent = df.tail(40)
    up_vol   = recent[recent['Close'] > recent['Open']]['Volume'].mean()
    down_vol = recent[recent['Close'] < recent['Open']]['Volume'].mean()
    return len(recent) > 20 and up_vol > down_vol * 1.4

def pretty_table(df):
    if df.empty:
        return "No setups today"
    h = "┌─────┬───┬───────┬───────┬─────┬──────┬───────┬─────┐"
    m = "├─────┼───┼───────┼───────┼─────┼──────┼───────┼─────┤"
    b = "└─────┴───┴───────┴───────┴─────┴──────┴───────┴─────┘"
    header = f"│{'TICK':<5}│{'MKT':<3}│{'PRICE':>7}│{'BUY':>7}│{'R%':>4}│{'SHR':>5}│{'CAP':>7}│{'WGT':>4}│"
    lines = [h, header, m]
    for _, r in df.iterrows():
        line = f"│{r['TICK']:<5}│{r['MKT']:<3}│{r['PRICE']:>7}│{r['BUY']:>7}│{r['R%']:>4}│{r['SHR']:>5}│{r['CAP']:>7}│{r['WGT']:>4}│"
        lines.append(line)
    lines.append(b)
    return "\n".join(lines)

# === MAIN SCAN ===
def run_scan(trigger="Scheduled"):
    send_whatsapp(f"US+HK MINERVINI SCAN STARTED — {now_hk()}\nTrigger: {trigger}")
    tickers = get_all_tickers()
    setups = []

    for i, t in enumerate(tickers):
        if i % 1000 == 0 and i > 0:
            send_whatsapp(f"Scanned {i:,}+ stocks...")
        try:
            df = yf.download(t, period="15mo", progress=False, auto_adjust=True)
            if len(df) < 150 or df['Close'].iloc[-1] < 5:
                continue

            price = df['Close'].iloc[-1]
            sma50  = df['Close'].rolling(50).mean().iloc[-1]
            sma200 = df['Close'].rolling(200).mean().iloc[-1]
            if not (price > sma50 > sma200):
                continue

            benchmark = "SPY" if not t.endswith('.HK') else "^HSI"
            market_df = yf.download(benchmark, period="3mo", progress=False)
            if len(df) < 21 or len(market_df) < 21:
                continue
            stock_ret  = df['Close'].iloc[-1] / df['Close'].iloc[-21]
            market_ret = market_df['Close'].iloc[-1] / market_df['Close'].iloc[-21]
            if stock_ret <= market_ret * 1.1:
                continue

            if not volume_bias_ok(df):
                continue

            pivot = df['High'][-40:].max() * 1.005
            if abs(price - pivot) / pivot > 0.12 and price < pivot:
                continue

            stop = max(df['Low'][-25:].min(), sma50 * 0.97)
            risk = (pivot - stop) / pivot
            if risk > 0.20:
                continue

            shares = math.floor(RISK_HKD / (pivot - stop))
            if shares < 20:
                continue

            capital_hkd = shares * pivot
            weight = round(capital_hkd / HKD_PORTFOLIO * 100, 1)
            market = "HK" if t.endswith('.HK') else "US"
            tick_display = t.replace('.HK', '') if market == "HK" else t

            setups.append({
                'TICK': tick_display,
                'MKT': market,
                'PRICE': f"{price:.2f}",
                'BUY': f"{pivot:.2f}",
                'R%': f"{risk*100:.1f}%",
                'SHR': shares,
                'CAP': f"{capital_hkd:,.0f}",
                'WGT': f"{weight}%"
            })
        except:
            continue
        time.sleep(0.05)

    setups = sorted(setups, key=lambda x: float(x['R%'][:-1]))
    table = pretty_table(pd.DataFrame(setups))
    total_w = sum(float(x['WGT'][:-1]) for x in setups)

    msg = f"*US + HK MINERVINI — {now_hk()}*\n"
    msg += f"*{len(setups)} SETUPS FOUND*\n"
    msg += f"Total exposure: *{total_w:.1f}%*\n\n"
    msg += f"```{table}```\n\n"
    msg += "No VCP • 4 core criteria only"

    send_whatsapp(msg)
    send_whatsapp(f"SCAN COMPLETE — {len(setups)} setups ready")
    print("Scan finished")

# ============ FLASK & SCHEDULER ============
from flask import Flask
app = Flask(__name__)

@app.route("/")
def home():
    threading.Thread(target=run_scan, args=("Manual",)).start()
    return f"<h1>US+HK Scan started — {now_hk()}</h1>"

threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), use_reloader=False), daemon=True).start()

# First run on deploy
run_scan("Deploy")

import schedule
schedule.every().day.at("08:25").do(lambda: run_scan("Daily"))
print("US + HK MINERVINI BOT STARTED — NO SYNTAX ERRORS")

while True:
    schedule.run_pending()
    time.sleep(60)
