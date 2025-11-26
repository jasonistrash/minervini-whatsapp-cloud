# main.py — BALANCED MINERVINI: 5 Core Criteria Only (High Hit Rate)
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
def now_hk(): return datetime.now(hk_tz).strftime("%d %b %Y %H:%M HK")

# ==================== CONFIG ====================
WHATSAPP_API_KEY = os.getenv('WHATSAPP_API_KEY')
PHONE_NUMBER     = os.getenv('PHONE_NUMBER')
HKD_PORTFOLIO    = float(os.getenv('HKD_PORTFOLIO', '3300000'))
HKD_TO_USD = 7.8
PORTFOLIO_USD = HKD_PORTFOLIO / HKD_TO_USD
RISK_USD = PORTFOLIO_USD * 0.005
# ===============================================

def send_whatsapp(msg):
    if not WHATSAPP_API_KEY or not PHONE_NUMBER: return
    try:
        requests.get("https://api.callmebot.com/whatsapp.php",
                     params={"phone": PHONE_NUMBER, "text": msg, "apikey": WHATSAPP_API_KEY}, timeout=15)
    except: pass

def get_tickers():
    try:
        nasdaq = pd.read_csv("https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/us_stock_symbols/nasdaq_full_tickers.csv")['Symbol'].tolist()
        nyse   = pd.read_csv("https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/us_stock_symbols/nyse_full_tickers.csv")['Symbol'].tolist()
        return [t for t in nasdaq + nyse if isinstance(t, str) and t.strip()]
    except: return ['SMCI','VST','APP','CELH','ELF','DUOL','APGE','ZYME','ARQT','MBX','RCUS','BLTE','COMP','TXG']

# Simple but effective VCP + volume bias
def has_vcp_and_volume_bias(df):
    recent = df.tail(60)
    high = recent['High'].max()
    high_idx = recent['High'].idxmax()
    base = recent.loc[high_idx:]

    # Volume bias: up days vs down days
    up_days = base[base['Close'] > base['Open']]
    down_days = base[base['Close'] < base['Open']]
    if len(up_days) < 3 or len(down_days) < 3: return False
    if up_days['Volume'].mean() <= down_days['Volume'].mean() * 1.5: return False

    # At least 2 contractions
    lows = base['Low'][base['Low'] == base['Low'].rolling(5, center=True).min()].dropna()
    if len(lows) < 2: return False
    contractions = [lows.iloc[i] > lows.iloc[i-1] * 1.02 for i in range(1, len(lows))]  # each low higher
    if sum(contractions[-3:]) < 2: return False

    return True

def pretty_table(df):
    if df.empty: return "No Minervini gems today"
    h = "┌─────┬───────┬───────┬───────┬─────┬──────┬────────┬───────┐"
    m = "├─────┼───────┼───────┼───────┼─────┼──────┼────────┼───────┤"
    b = "└─────┴───────┴───────┴───────┴─────┴──────┴────────┴───────┘"
    header = f"│{'TICK':<5}│{'PRICE':>7}│{'BUY':>7}│{'STOP':>7}│{'R%':>4}│{'SHR':>5}│{'CAP':>7}│{'WGT':>5}│"
    lines = [h, header, m]
    for _, r in df.iterrows():
        line = f"│{r['TICK']:<5}│{r['PRICE']:>7}│{r['BUY']:>7}│{r['STOP']:>7}│{r['R%']:>4}│{r['SHR']:>5}│{r['CAP']:>7}│{r['WGT']:>5}│"
        lines.append(line)
    lines.append(b)
    return "\n".join(lines)

def run_scan(trigger="Scheduled"):
    send_whatsapp(f"MINERVINI SCAN STARTED — {now_hk()}\n5 Core Criteria Only | Trigger: {trigger}")
    tickers = get_tickers()
    setups = []

    for i, t in enumerate(tickers):
        if i % 800 == 0 and i > 0:
            send_whatsapp(f"Scanned {i:,}+ stocks...")
        try:
            df = yf.download(t, period="15mo", progress=False, auto_adjust=True)
            if len(df) < 200 or df['Close'].iloc[-1] < 10: continue

            price = df['Close'].iloc[-1]
            sma50 = df['Close'].rolling(50).mean().iloc[-1]
            sma200 = df['Close'].rolling(200).mean().iloc[-1]
            if not (price > sma50 > sma200): continue

            # 1. Recent outperformance (1 month)
            spy = yf.download("SPY", period="3mo", progress=False)
            if len(df) < 21 or len(spy) < 21: continue
            stock_ret = df['Close'].iloc[-1] / df['Close'].iloc[-21]
            spy_ret = spy['Close'].iloc[-1] / spy['Close'].iloc[-21]
            if stock_ret <= spy_ret * 1.1: continue

            # 2. Volume bias + VCP
            if not has_vcp_and_volume_bias(df): continue

            # 3. Pivot & proximity
            pivot = df['High'][-40:].max() * 1.005
            if abs(price - pivot) / pivot > 0.08 and price < pivot: continue  # not within ±8%

            stop = max(df['Low'][-25:].min(), sma50 * 0.97)
            risk = (pivot - stop) / pivot
            if risk > 0.15: continue

            shares = math.floor(RISK_USD / (pivot - stop))
            if shares < 20: continue
            capital = shares * pivot
            weight = round(capital / PORTFOLIO_USD * 100, 1)

            setups.append({
                'TICK': t,
                'PRICE': f"{price:.2f}",
                'BUY': f"{pivot:.2f}",
                'STOP': f"{stop:.2f}",
                'R%': f"{risk*100:.1f}%",
                'SHR': shares,
                'CAP': f"${capital:,.0f}",
                'WGT': f"{weight}%"
            })
        except: continue
        time.sleep(0.06)

    setups = sorted(setups, key=lambda x: float(x['R%'][:-1]))
    table = pretty_table(pd.DataFrame(setups))
    total_w = sum(float(x['WGT'][:-1]) for x in setups)

    msg = f"*MINERVINI GEMS — {now_hk()}*\n"
    msg += f"*{len(setups)} HIGH-PROBABILITY SETUPS*\nTotal exposure: *{total_w:.1f}%*\n\n"
    msg += f"```{table}```\n\n"
    msg += "5 Core Criteria Only — Pure Minervini"

    send_whatsapp(msg)
    send_whatsapp(f"SCAN COMPLETE — {len(setups)} ready to rock")
    print(f"Done — {len(setups)} gems found")

# ============ FLASK & SCHEDULER ============
from flask import Flask
app = Flask(__name__)
@app.route("/"); threading.Thread(target=run_scan, args=("Manual",)).start(); return f"<h1>Scan Running...</h1><p>Check WhatsApp<br>{now_hk()}</p>"
threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)), use_reloader=False), daemon=True).start()

run_scan("Deploy")
import schedule
schedule.every().day.at("08:25").do(lambda: run_scan("Daily"))
print("BALANCED MINERVINI BOT LIVE — 5 CORE CRITERIA")
while True: schedule.run_pending(); time.sleep(60)
