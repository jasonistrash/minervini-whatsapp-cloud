# main.py — PURE MINERVINI: No limits, no caps, full market, HK time
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
RISK_USD = PORTFOLIO_USD * 0.005  # 0.5% risk per trade — fixed forever
# ===============================================

def send_whatsapp(msg):
    if not all([WHATSAPP_API_KEY, PHONE_NUMBER]): return
    try:
        requests.get("https://api.callmebot.com/whatsapp.php",
                     params={"phone": PHONE_NUMBER, "text": msg, "apikey": WHATSAPP_API_KEY},
                     timeout=15)
        print("WhatsApp sent")
    except: print("WhatsApp failed")

def get_all_tickers():
    try:
        nasdaq = pd.read_csv("https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/us_stock_symbols/nasdaq_full_tickers.csv")['Symbol'].dropna().tolist()
        nyse   = pd.read_csv("https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/us_stock_symbols/nyse_full_tickers.csv")['Symbol'].dropna().tolist()
        return [t for t in nasdaq + nyse if isinstance(t, str) and t.strip()]
    except:
        return ['AAPL','NVDA','SMCI','CELH','ELF','DUOL','VST','APP','APGE','ZYME','ARQT','INDV','MBX']

def pretty_table(df):
    if df.empty: return "No pure Minervini setups today"
    h = "┌─────┬───────┬───────┬───────┬─────┬──────┬────────┬───────┐"
    m = "├─────┼───────┼───────┼───────┼─────┼──────┼────────┼───────┤"
    b = "└─────┴───────┴───────┴───────┴─────┴──────┴────────┴───────┘"
    header = f"│{'TICK':<5}│{'PRICE':>7}│{'BUY':>7}│{'STOP':>7}│{'R%':>4}│{'SHARE':>6}│{'CAPITAL':>8}│{'WEIGHT':>6}│"
    lines = [h, header, m]
    for _, r in df.iterrows():
        line = f"│{r['TICK']:<5}│{r['PRICE']:>7}│{r['BUY']:>7}│{r['STOP']:>7}│{r['R%']:>4}│{r['SHARE']:>6}│{r['CAPITAL']:>8}│{r['WEIGHT']:>6}│"
        lines.append(line)
    lines.append(b)
    return "\n".join(lines)

def run_screen(trigger="Scheduled"):
    send_whatsapp(f"MINERVINI SCAN STARTED — {now_hk()}\nTrigger: {trigger}\nFull US market scan (~8,000 stocks)")

    tickers = get_all_tickers()
    setups = []

    for i, t in enumerate(tickers):
        if i % 1000 == 0 and i > 0:
            send_whatsapp(f"Scanned {i:,}+ stocks...")
        try:
            info = yf.Ticker(t).info
            price = info.get('regularMarketPrice') or info.get('previousClose')
            if not price or price < 10 or info.get('averageVolume',0) < 300000: continue

            df = yf.Ticker(t).history(period="15mo")
            if len(df) < 200: continue
            sma50  = df['Close'].rolling(50).mean().iloc[-1]
            sma200 = df['Close'].rolling(200).mean().iloc[-1]
            if not (price > sma50 > sma200): continue

            spy_ret = (yf.Ticker("SPY").history(period="1y")['Close'].iloc[-1] / yf.Ticker("SPY").history(period="1y")['Close'].iloc[0]) - 1
            stock_ret = df['Close'].iloc[-1] / df['Close'].iloc[-252] - 1
            if stock_ret < spy_ret * 1.3: continue

            buy_point = round(df['High'][-35:].max() * 1.005, 2)
            if buy_point <= price: continue
            stop = round(max(df['Low'][-25:].min(), sma50 * 0.975), 2)
            risk_pct = round((buy_point - stop) / buy_point * 100, 1)
            if risk_pct > 11: continue

            shares = math.floor(RISK_USD / (buy_point - stop))
            if shares < 25: continue

            capital = shares * buy_point
            weight = round(capital / PORTFOLIO_USD * 100, 2)

            setups.append({
                'TICK': t,
                'PRICE': f"{price:.2f}",
                'BUY': f"{buy_point:.2f}",
                'STOP': f"{stop:.2f}",
                'R%': f"{risk_pct}%",
                'SHARE': shares,
                'CAPITAL': f"${capital:,.0f}",
                'WEIGHT': f"{weight}%"
            })
        except:
            continue
        time.sleep(0.07)

    # Pure Minervini: sort by lowest risk first — take ALL that qualify
    setups = sorted(setups, key=lambda x: float(x['R%'][:-1]))

    total_weight = sum(float(x['WEIGHT'][:-1]) for x in setups)

    table = pretty_table(pd.DataFrame(setups))
    msg = f"*MARK MINERVINI SETUPS — {now_hk()}*\n"
    msg += f"*{len(setups)} PURE SETUPS FOUND* (no limits)\n"
    msg += f"Total exposure if all taken: *{total_weight:.1f}%*\n\n"
    msg += f"```{table}```\n\n"
    msg += f"HKD {HKD_PORTFOLIO:,.0f} → 0.5% risk per trade | Real Minervini style"

    send_whatsapp(msg)
    send_whatsapp(f"SCAN COMPLETE — {len(setups)} setups ready")
    print(f"Done — {len(setups)} pure Minervini setups")

# ============ FLASK (manual trigger) ============
from flask import Flask
app = Flask(__name__)

@app.route("/")
def home():
    threading.Thread(target=run_screen, args=("Manual",)).start()
    return f"<h1>Full Minervini scan triggered!</h1><p>Check WhatsApp in 4–8 min<br>{now_hk()}</p>"

@app.route("/status")
def status():
    return f"<h2>Minervini Bot LIVE — HK Time</h2>No limits · Pure criteria<br>Portfolio: HKD {HKD_PORTFOLIO:,.0f}<br>{now_hk()}"

threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)), use_reloader=False), daemon=True).start()

# ============ DAILY 8:25 AM HONG KONG ============
run_screen("Deploy")
import schedule
schedule.every().day.at("08:25").do(lambda: run_screen("Daily"))

print("PURE MINERVINI BOT RUNNING — NO LIMITS — HK TIME")
while True:
    schedule.run_pending()
    time.sleep(60)
