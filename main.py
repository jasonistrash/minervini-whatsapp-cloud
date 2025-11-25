# main.py — UPDATED: Recent RS (1m/week) + Volume 1.3x + Dual Scan (Last Close + Live)
import os
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
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
RISK_USD = PORTFOLIO_USD * 0.005  # 0.5% risk per trade
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
        return ['AAPL','NVDA','SMCI','CELH','ELF','DUOL','VST','APP','APGE','ZYME','ARQT','INDV','MBX','RCUS','TXG','COMP','BTE']

def pretty_table(df):
    if df.empty: return "No Minervini setups today"
    h = "┌─────┬───────┬───────┬───────┬─────┬──────┬────────┬───────┐"
    m = "├─────┼───────┼───────┼───────┼─────┼───────┼────────┼───────┤"
    b = "└─────┴───────┴───────┴───────┴─────┴───────┴────────┴───────┘"
    header = f"│{'TICK':<5}│{'PRICE':>7}│{'BUY':>7}│{'STOP':>7}│{'R%':>4}│{'SHARE':>6}│{'CAPITAL':>8}│{'WEIGHT':>6}│"
    lines = [h, header, m]
    for _, r in df.iterrows():
        line = f"│{r['TICK']:<5}│{r['PRICE']:>7}│{r['BUY']:>7}│{r['STOP']:>7}│{r['R%']:>4}│{r['SHARE']:>6}│{r['CAPITAL']:>8}│{r['WEIGHT']:>6}│"
        lines.append(line)
    lines.append(b)
    return "\n".join(lines)

def get_data_for_scan(scan_type):
    """Get data: 'last_close' for previous day, 'live' for current/intraday"""
    if scan_type == 'last_close':
        end_date = datetime.now(hk_tz) - timedelta(days=1)
        start_date = end_date - timedelta(days=450)  # ~15mo back
        df = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)
        if df.empty:
            return None
        price = df['Close'].iloc[-1]  # Last close price
        yesterday_vol = df['Volume'].iloc[-1]
        df_vol = df['Volume'].tail(11)  # Last 10 + yesterday
        avg_vol_10d = df_vol.iloc[:-1].mean() if len(df_vol) > 10 else 0
        return df, price, yesterday_vol, avg_vol_10d
    else:  # live
        df = yf.download(ticker, period='15mo', progress=False)
        if df.empty:
            return None
        price = df['Close'].iloc[-1]  # Current close/live price
        # For live volume: use latest available (yesterday if pre-market, today if open)
        yesterday_vol = df['Volume'].iloc[-1]
        df_vol = df['Volume'].tail(11)
        avg_vol_10d = df_vol.iloc[:-1].mean() if len(df_vol) > 10 else 0
        return df, price, yesterday_vol, avg_vol_10d

def run_single_scan(scan_type, trigger="Scheduled"):
    send_whatsapp(f"MINERVINI {scan_type.upper()} SCAN STARTED — {now_hk()}\nTrigger: {trigger}")
    
    tickers = get_all_tickers()
    setups = []

    for i, ticker in enumerate(tickers):
        if i % 1000 == 0 and i > 0:
            send_whatsapp(f"{scan_type} Scan: {i:,}+ stocks checked...")
        try:
            data = get_data_for_scan(scan_type)
            if not data:
                continue
            df, price, yesterday_vol, avg_vol_10d = data
            
            if price < 10 or avg_vol_10d < 300000: continue
            if yesterday_vol <= avg_vol_10d * 1.3: continue  # New volume filter

            sma50  = df['Close'].rolling(50).mean().iloc[-1]
            sma200 = df['Close'].rolling(200).mean().iloc[-1]
            if not (price > sma50 > sma200): continue

            # New RS: Recent 1-month outperformance vs SPY
            spy_df = yf.download('SPY', period='3mo', progress=False)
            if len(spy_df) < 21:
                continue
            stock_1m = (df['Close'].iloc[-1] / df['Close'].iloc[-21]) - 1
            spy_1m = (spy_df['Close'].iloc[-1] / spy_df['Close'].iloc[-21]) - 1
            if stock_1m <= spy_1m * 1.3:
                # Fallback to 1-week if 1m data short
                if len(df) >= 5:
                    stock_1w = (df['Close'].iloc[-1] / df['Close'].iloc[-5]) - 1
                    spy_1w = (spy_df['Close'].iloc[-1] / spy_df['Close'].iloc[-5]) - 1
                    if stock_1w > spy_1w * 1.3:
                        pass
                    else:
                        continue
                else:
                    continue

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
                'TICK': ticker,
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

    setups = sorted(setups, key=lambda x: float(x['R%'][:-1]))
    total_weight = sum(float(x['WEIGHT'][:-1]) for x in setups)

    table = pretty_table(pd.DataFrame(setups))
    msg = f"*MINERVINI {scan_type.upper()} SCAN — {now_hk()}*\n"
    msg += f"*{len(setups)} PURE SETUPS* (recent RS + volume 1.3x)\n"
    msg += f"Total exposure: *{total_weight:.1f}%*\n\n"
    msg += f"```{table}```\n\n"
    msg += f"HKD {HKD_PORTFOLIO:,.0f} → 0.5% risk/trade | Pure Minervini"

    send_whatsapp(msg)
    send_whatsapp(f"{scan_type.upper()} SCAN COMPLETE — {len(setups)} setups")
    print(f"{scan_type} scan done: {len(setups)} setups")

def run_screen(trigger="Scheduled"):
    # Run both scans
    run_single_scan('last_close', trigger)
    time.sleep(5)  # Small delay between scans
    run_single_scan('live', trigger)

# ============ FLASK (manual trigger) ============
from flask import Flask
app = Flask(__name__)

@app.route("/")
def home():
    threading.Thread(target=run_screen, args=("Manual",)).start()
    return f"<h1>Dual Minervini scan triggered!</h1><p>Last Close + Live | Check WhatsApp in 8–15 min<br>{now_hk()}</p>"

@app.route("/status")
def status():
    return f"<h2>Minervini Bot LIVE — HK Time</h2>Recent RS (1m/week) + Vol 1.3x<br>Portfolio: HKD {HKD_PORTFOLIO:,.0f}<br>{now_hk()}"

threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)), use_reloader=False), daemon=True).start()

# ============ DAILY 8:25 AM HONG KONG ============
run_screen("Deploy")
import schedule
schedule.every().day.at("08:25").do(lambda: run_screen("Daily"))

print("UPDATED MINERVINI BOT — RECENT RS + VOLUME + DUAL SCAN — HK TIME")
while True:
    schedule.run_pending()
    time.sleep(60)
