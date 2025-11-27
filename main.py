# main.py — DOUBLE SCANNER: Minervini Pivot (1.2× vol) + O'Neil CANSLIM
import os
import yfinance as yf
import pandas as pd
import requests
import threading
import math
import time
import schedule
from datetime import datetime
from zoneinfo import ZoneInfo

hk_tz = ZoneInfo("Asia/Hong_Kong")
def now_hk():
    return datetime.now(hk_tz).strftime("%d %b %Y %H:%M HK")

# ==================== CONFIG ====================
WHATSAPP_API_KEY = os.getenv('WHATSAPP_API_KEY')
PHONE_NUMBER     = os.getenv('PHONE_NUMBER')
HKD_PORTFOLIO    = float(os.getenv('HKD_PORTFOLIO', '3300000'))
RISK_HKD         = HKD_PORTFOLIO * 0.005

def send_whatsapp(msg):
    if not WHATSAPP_API_KEY or not PHONE_NUMBER:
        return
    # Fixed: proper indentation
        return
    url = "https://api.callmebot.com/whatsapp.php"
    params = {"phone": PHONE_NUMBER, "text": msg, "apikey": WHATSAPP_API_KEY}
    try:
        requests.get(url, params=params, timeout=15)
    except Exception:
        pass

# ==================== TICKERS ====================
def get_all_tickers():
    us = []
    try:
        nasdaq = pd.read_csv("https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/us_stock_symbols/nasdaq_full_tickers.csv")['Symbol'].tolist()
        nyse   = pd.read_csv("https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/us_stock_symbols/nyse_full_tickers.csv")['Symbol'].tolist()
        us = [t for t in nasdaq + nyse if isinstance(t, str) and t.strip()]
    except Exception:
        us = []

    hk = []
    try:
        df = pd.read_csv("https://raw.githubusercontent.com/rreichel3/HK-Stock-Symbols/main/hk_stock_symbols.csv")
        hk = [f"{row.Symbol}.HK" for row in df.itertuples() if str(row.Symbol).isdigit()]
    except Exception:
        hk = ['0700.HK', '9988.HK', '3690.HK']

    return us + hk

# ==================== MINERVINI PIVOT (1.2× volume) ====================
def minervini_pivot_scan(tickers):
    setups = []
    for i, t in enumerate(tickers):
        if i % 800 == 0 and i > 0:
            send_whatsapp(f"Minervini scanned {i:,}+ stocks...")
        try:
            df = yf.download(t, period="15mo", progress=False, auto_adjust=True)
            if len(df) < 200 or df['Close'].iloc[-1] < 8:
                continue

            price  = df['Close'].iloc[-1]
            sma50  = df['Close'].rolling(50).mean().iloc[-1]
            sma200 = df['Close'].rolling(200).mean().iloc[-1]
            if not (price > sma50 > sma200):
                continue

            base_high = df['High'][:-5].max()
            today_high = df['High'].iloc[-1]
            today_vol  = df['Volume'].iloc[-1]
            avg_vol50  = df['Volume'].tail(50).mean()

            if today_high >= base_high and today_vol >= avg_vol50 * 1.2:
                buy_point = base_high * 1.005
                stop = max(df['Low'][-25:].min(), sma50 * 0.95)
                risk_pct = (buy_point - stop) / buy_point
                if risk_pct > 0.08:
                    continue

                shares = math.floor(RISK_HKD / (buy_point - stop))
                if shares < 20:
                    continue
                weight = round(shares * buy_point / HKD_PORTFOLIO * 100, 1)

                market = "HK" if t.endswith('.HK') else "US"
                tick   = t.replace('.HK', '') if market == "HK" else t

                setups.append([tick, market, f"{price:.2f}", f"{buy_point:.2f}",
                              f"{risk_pct*100:.1f}%", shares, f"{weight}%"])
        except Exception:
            continue
        time.sleep(0.05)
    return setups

# ==================== O'NEIL CANSLIM ====================
def canslim_scan(tickers):
    leaders = []
    try:
        spy_hist = yf.download("SPY", period="6mo", progress=False)
    except Exception:
        return leaders

    for i, t in enumerate(tickers):
        if i % 800 == 0 and i > 0:
            send_whatsapp(f"CANSLIM scanned {i:,}+ stocks...")
        try:
            df = yf.download(t, period="2y", progress=False, auto_adjust=True)
            if len(df) < 400 or df['Close'].iloc[-1] < 15:
                continue

            price   = df['Close'].iloc[-1]
            sma50  = df['Close'].rolling(50).mean().iloc[-1]
            sma150 = df['Close'].rolling(150).mean().iloc[-1]
            sma200 = df['Close'].rolling(200).mean().iloc[-1]

            if not (price > sma150 > sma200):
                continue
            if price < sma50 * 0.75:
                continue

            if len(df) > 63:
                ret_stock = price / df['Close'].iloc[-63]
                ret_spy   = spy_hist['Close'].iloc[-1] / spy_hist['Close'].iloc[-63]
                if ret_stock < ret_spy * 1.2:
                    continue

            vol50 = df['Volume'].tail(50).mean()
            if df['Volume'].tail(3).mean() < vol50 * 1.2:
                continue

            market = "HK" if t.endswith('.HK') else "US"
            tick   = t.replace('.HK', '') if market == "HK" else t
            leaders.append([tick, market, f"{price:.2f}", f"{sma50:.2f}", f"{(ret_stock-1)*100:.1f}%"])
        except Exception:
            continue
        time.sleep(0.05)

    leaders.sort(key=lambda x: float(x[4][:-1]), reverse=True)
    return leaders[:30]

# ==================== TABLES ====================
def minervini_table(rows):
    if not rows:
        return "No Minervini pivots today"
    lines = [
        "┌─────┬───┬───────┬───────┬─────┬──────┐",
        "│TICK │MKT│ PRICE │ BUY │ R% │ WGT │",
        "├─────┼───┼───────┼───────┼─────┼──────┤"
    ]
    for r in rows:
        lines.append(f"│{r[0]:<5}│{r[1]:<3}│{r[2]:>7}│{r[3]:>7}│{r[4]:>4}│{r[6]:>5}│")
    lines.append("└─────┴───┴───────┴───────┴─────┴──────┘")
    return "\n".join(lines)

def canslim_table(rows):
    if not rows:
        return "No CANSLIM leaders today"
    lines = [
        "┌─────┬───┬───────┬───────┬──────┐",
        "│TICK │MKT│ PRICE │ SMA50 │ 3M% │",
        "├─────┼───┼───────┼───────┼──────┤"
    ]
    for r in rows:
        lines.append(f"│{r[0]:<5}│{r[1]:<3}│{r[2]:>7}│{r[3]:>7}│{r[4]:>5}│")
    lines.append("└─────┴───┴───────┴───────┴──────┘")
    return "\n".join(lines)

# ==================== FULL SCAN ====================
def full_scan():
    send_whatsapp(f"DOUBLE SCAN STARTED — {now_hk()}")
    tickers = get_all_tickers()

    minervini = minervini_pivot_scan(tickers)
    send_whatsapp(f"*MINERVINI PIVOTS (1.2× vol) — {now_hk()}*\n{len(minervini)} setups\n\n```{minervini_table(minervini)}```")

    canslim = canslim_scan(tickers)
    send_whatsapp(f"*O'NEIL CANSLIM LEADERS — {now_hk()}*\n{len(canslim)} leaders\n\n```{canslim_table(canslim)}```")

    send_whatsapp("Both scans completed!")

# ==================== FLASK ====================
from flask import Flask
app = Flask(__name__)

@app.route("/")
def home():
    threading.Thread(target=full_scan).start()
    return f"<h1>Double Scanner Running… Check WhatsApp!</h1><p>{now_hk()}</p>"

# ==================== RUN ====================
if __name__ == "__main__":
    full_scan()
    schedule.every().day.at("08:25").do(full_scan)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
