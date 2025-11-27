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

# === PROPER PIVOT DETECTION (TraderLion / Minervini) ===
def is_valid_pivot_breakout(df, lookback=70):
    recent = df.tail(lookback).copy()
    if len(recent) < 50:
        return False, 0

    # Find base high (prior resistance) — ignore last few days
    base_high = recent['High'][:-5].max()
    base_high_idx = recent['High'][:-5].idxmax()
    left  = recent.loc[:base_high_idx]
    right = recent.loc[base_high_idx:]

    if len(left) < 15 or len(right) < 10:
        return False, 0

    # 1. Price range must tighten right side
    left_range  = left['High'].max() - left['Low'].min()
    right_range = right['High'].max() - right['Low'].min()
    if right_range > left_range * 0.75:
        return False, 0

    # 2. Volume must dry up in the handle/tight area
    recent_vol  = recent['Volume'].iloc[-20:].mean()
    earlier_vol = recent['Volume'].iloc[-40:-20].mean()
    if recent_vol > earlier_vol * 0.75:
        return False, 0

    # 3. Breakout above base_high on volume surge
    today_high = recent['High'].iloc[-1]
    today_vol  = recent['Volume'].iloc[-1]
    avg_vol    = recent['Volume'].tail(50).mean()

    if today_high >= base_high and today_vol >= avg_vol * 1.5:
        return True, base_high * 1.005  # buy slightly above pivot

    return False, 0

# === VOLUME BIAS ===
def volume_bias_ok(df):
    recent = df.tail(40)
    up   = recent[recent['Close'] > recent['Open']]['Volume'].mean()
    down = recent[recent['Close'] < recent['Open']]['Volume'].mean()
    return up >= down * 1.4

# === TABLE ===
def pretty_table(df):
    if df.empty:
        return "No elite pivots today"
    h = "┌─────┬───┬───────┬───────┬─────┬──────┬───────┐"
    m = "├─────┼───┼───────┼───────┼─────┼──────┼───────┤"
    b = "└─────┴───┴───────┴───────┴─────┴──────┴───────┘"
    header = f"│{'TICK':<5}│{'MKT':<3}│{'PRICE':>7}│{'BUY':>7}│{'R%':>4}│{'SHR':>5}│{'WGT':>5}│"
    lines = [h, header, m]
    for _, r in df.iterrows():
        line = f"│{r['TICK']:<5}│{r['MKT']:<3}│{r['PRICE']:>7}│{r['BUY']:>7}│{r['R%']:>4}│{r['SHR']:>5}│{r['WGT']:>5}│"
        lines.append(line)
    lines.append(b)
    return "\n".join(lines)

# === SCAN ===
def run_scan(trigger="Scheduled"):
    send_whatsapp(f"ELITE PIVOT SCAN STARTED — {now_hk()}\n3 Criteria Only • Proper Minervini Pivots")
    tickers = get_all_tickers()
    setups = []

    for i, t in enumerate(tickers):
        if i % 800 == 0 and i > 0:
            send_whatsapp(f"Scanned {i:,}+ stocks...")
        try:
            df = yf.download(t, period="15mo", progress=False, auto_adjust=True)
            if len(df) < 200 or df['Close'].iloc[-1] < 8:
                continue

            price = df['Close'].iloc[-1]
            sma50 = df['Close'].rolling(50).mean().iloc[-1]
            sma200 = df['Close'].rolling(200).mean().iloc[-1]
            if not (price > sma50 > sma200):
                continue

            if not volume_bias_ok(df):
                continue

            is_pivot, buy_point = is_valid_pivot_breakout(df)
            if not is_pivot:
                continue

            stop = max(df['Low'][-25:].min(), sma50 * 0.95)
            risk_pct = (buy_point - stop) / buy_point
            if risk_pct > 0.08:
                continue

            shares = math.floor(RISK_HKD / (buy_point - stop))
            if shares < 20:
                continue
            weight = round(shares * buy_point / HKD_PORTFOLIO * 100, 1)

            market = "HK" if t.endswith('.HK') else "US"
            tick = t.replace('.HK', '') if market == "HK" else t

            setups.append({
                'TICK': tick,
                'MKT': market,
                'PRICE': f"{price:.2f}",
                'BUY': f"{buy_point:.2f}",
                'R%': f"{risk_pct*100:.1f}%",
                'SHR': shares,
                'WGT': f"{weight}%"
            })
        except:
            continue
        time.sleep(0.05)

    setups = sorted(setups, key=lambda x: float(x['R%'][:-1]))
    table = pretty_table(pd.DataFrame(setups))
    total_w = sum(float(x['WGT'][:-1]) for x in setups)

    msg = f"*ELITE MINERVINI PIVOTS — {now_hk()}*\n"
    msg += f"*{len(setups)} TRUE PIVOT BREAKOUTS*\nTotal exposure: {total_w:.1f}%\n\n"
    msg += f"```{table}```\n\n"
    msg += "Stage 2 • Volume Bias • Proper Pivot Breakout ≤8% Risk"

    send_whatsapp(msg)
    send_whatsapp(f"SCAN COMPLETE — {len(setups)} monsters ready")
    print(f"Done — {len(setups)} elite setups")

# === FLASK & SCHEDULER ===
from flask import Flask
app = Flask(__name__)

@app.route("/")
def home():
    threading.Thread(target=run_scan, args=("Manual",)).start()
    return f"<h1>Elite Pivot Scan Running...</h1><p>{now_hk()}</p>"

threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), use_reloader=False), daemon=True).start()

run_scan("Deploy")
import schedule
schedule.every().day.at("08:25").do(lambda: run_scan("Daily"))
print("ELITE MINERVINI PIVOT BOT LIVE — FINAL VERSION")

while True:
    schedule.run_pending()
    time.sleep(60)
