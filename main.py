# main.py — TWO SCANS: 1) Minervini Pivot (1.2x vol)  2) O'Neil CANSLIM
import os, yfinance as yf, pandas as pd, requests, threading, math, time
from datetime import datetime
from zoneinfo import ZoneInfo

hk_tz = ZoneInfo("Asia/Hong_Kong")
def now_hk(): return datetime.now(hk_tz).strftime("%d %b %Y %H:%M HK")

WHATSAPP_API_KEY = os.getenv('WHATSAPP_API_KEY')
PHONE_NUMBER     = os.getenv('PHONE_NUMBER')
HKD_PORTFOLIO    = float(os.getenv('HKD_PORTFOLIO', '3300000'))
RISK_HKD         = HKD_PORTFOLIO * 0.005

def send_whatsapp(msg):
    if not WHATSAPP_API_KEY or not PHONE_NUMBER: return
    try:
        requests.get("https://api.callmebot.com/whatsapp.php",
                     params={"phone": PHONE_NUMBER, "text": msg, "apikey": WHATSAPP_API_KEY}, timeout=15)
    except: pass

# === TICKERS (US + HK) ===
def get_all_tickers():
    us = []
    try:
        nasdaq = pd.read_csv("https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/us_stock_symbols/nasdaq_full_tickers.csv")['Symbol'].tolist()
        nyse   = pd.read_csv("https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/us_stock_symbols/nyse_full_tickers.csv")['Symbol'].tolist()
        us = [t for t in nasdaq + nyse if isinstance(t,str) and t.strip()]
    except: pass
    hk = []
    try:
        df = pd.read_csv("https://raw.githubusercontent.com/rreichel3/HK-Stock-Symbols/main/hk_stock_symbols.csv")
        hk = [f"{row.Symbol}.HK" for row in df.itertuples() if str(row.Symbol).isdigit()]
    except: hk = ['0700.HK','9988.HK','3690.HK']
    return us + hk

# === MINERVINI PIVOT (volume loosened to 1.2x) ===
def minervini_pivot_scan(tickers):
    setups = []
    for i,t in enumerate(tickers):
        if i%800==0 and i>0: send_whatsapp(f"Minervini scanned {i:,}+...")
        try:
            df = yf.download(t, period="15mo", progress=False, auto_adjust=True)
            if len(df)<200 or df['Close'].iloc[-1]<8: continue
            price = df['Close'].iloc[-1]
            sma50 = df['Close'].rolling(50).mean().iloc[-1]
            sma200= df['Close'].rolling(200).mean().iloc[-1]
            if not (price > sma50 > sma200): continue

            # Proper pivot + volume loosened to 1.2x
            base_high = df['High'][:-5].max()
            today_high = df['High'].iloc[-1]
            today_vol  = df['Volume'].iloc[-1]
            avg_vol    = df['Volume'].tail(50).mean()
            if today_high >= base_high and today_vol >= avg_vol * 1.2:
                buy = base_high * 1.005
                stop = max(df['Low'][-25:].min(), sma50*0.95)
                risk = (buy-stop)/buy
                if risk > 0.08: continue
                shares = math.floor(RISK_HKD/(buy-stop))
                if shares<20: continue
                weight = round(shares*buy/HKD_PORTFOLIO*100,1)
                mkt = "HK" if t.endswith('.HK') else "US"
                tick = t.replace('.HK','') if mkt=="HK" else t
                setups.append([tick,mkt,f"{price:.2f}",f"{buy:.2f}",f"{risk*100:.1f}%",shares,f"{weight}%"])
        except: continue
        time.sleep(0.05)
    return setups

# === O'NEIL CANSLIM (pure IBD leaders) ===
def canslim_scan(tickers):
    leaders = []
    for i,t in enumerate(tickers):
        if i%800==0 and i>0: send_whatsapp(f"CANSLIM scanned {i:,}+...")
        try:
            df = yf.download(t, period="2y", progress=False, auto_adjust=True)
            if len(df)<400: continue
            price = df['Close'].iloc[-1]
            if price<15: continue
            sma50 = df['Close'].rolling(50).mean().iloc[-1]
            sma150= df['Close'].rolling(150).mean().iloc[-1]
            sma200= df['Close'].rolling(200).mean().iloc[-1]
            if not (price > sma150 > sma200): continue
            if price < sma50*0.75: continue

            # RS rating proxy: 3-month vs SPY
            spy = yf.download("SPY", period="6mo", progress=False)
            ret_stock = price / df['Close'].iloc[-63] if len(df)>63 else 1
            ret_spy   = spy['Close'].iloc[-1] / spy['Close'].iloc[-63]
            if ret_stock < ret_spy * 1.2: continue

            # Volume surge last 3 days
            vol_avg50 = df['Volume'].tail(50).mean()
            if df['Volume'].tail(3).mean() < vol_avg50*1.2: continue

            mkt = "HK" if t.endswith('.HK') else "US"
            tick = t.replace('.HK','') if mkt=="HK" else t
            leaders.append([tick,mkt,f"{price:.2f}",f"{sma50:.2f}",f"{ret_stock*100-100:.1f}%","RS+"])
        except: continue
        time.sleep(0.05)
    return sorted(leaders, key=lambda x: float(x[4][:-1]), reverse=True)[:30]

# === PRETTY TABLES ===
def table(txt, rows, headers):
    if not rows: return f"No {txt} today"
    h = "┌─────┬───┬───────┬───────┬─────┬──────┐"
    m = "├─────┼───┼───────┼───────┼─────┼──────┤"
    b = "└─────┴───┴───────┴───────┴─────┴──────┘"
    lines = [h, f"│{'TICK':<5}│{'MKT':<3}│{'PRICE':>7}│{'BUY':>7}│{'R%':>4}│{'WGT':>5}│", m]
    for r in rows:
        lines.append(f"│{r[0]:<5}│{r[1]:<3}│{r[2]:>7}│{r[3]:>7}│{r[4]:>4}│{r[5]:>5}│")
    lines.append(b)
    return "\n".join(lines)

def canslim_table(rows):
    if not rows: return "No CANSLIM leaders today"
    h = "┌─────┬───┬───────┬───────┬──────┐"
    m = "├─────┼───┼───────┼───────┼──────┤"
    b = "└─────┴───┴───────┴───────┴──────┘"
    lines = [h, f"│{'TICK':<5}│{'MKT':<3}│{'PRICE':>7}│{'SMA50':>7}│{'3M%':>5}│", m]
    for r in rows:
        lines.append(f"│{r[0]:<5}│{r[1]:<3}│{r[2]:>7}│{r[3]:>7}│{r[4]:>5}│")
    lines.append(b)
    return "\n".join(lines)

# === MAIN RUN ===
def full_scan():
    send_whatsapp(f"FULL SCAN STARTED — {now_hk()}")
    tickers = get_all_tickers()

    # 1. Minervini Pivot (1.2x volume)
    minervini = minervini_pivot_scan(tickers)
    msg1 = f"*MINERVINI PIVOT MONSTERS (1.2× vol) — {now_hk()}*\n{len(minervini)} setups\n\n```{table('Minervini', minervini, None)}```"
    send_whatsapp(msg1)

    # 2. O'Neil CANSLIM
    canslim = canslim_scan(tickers)
    msg2 = f"*O'NEIL CANSLIM LEADERS — {now_hk()}*\n{len(canslim)} leaders\n\n```{canslim_table(canslim)}```"
    send_whatsapp(msg2)

    send_whatsapp("Both scans complete!")

from flask import Flask
app = Flask(__name__)
@app.route("/"): threading.Thread(target=full_scan).start(); return f"<h1>Double Scan Running… Check WhatsApp!</h1><p>{now_hk()}</p>"

full_scan()  # on deploy
import schedule
schedule.every().day.at("08:25").do(full_scan)
print("DOUBLE ELITE SCANNER LIVE")
while True: schedule.run_pending(); time.sleep(60)
