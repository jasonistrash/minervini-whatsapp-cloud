# main.py - Minervini Daily Screener for Render + WhatsApp
import os
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime
import time
import math
import schedule  # For cron-like scheduling on Render

# Config from Render Environment Variables
WHATSAPP_API_KEY = os.getenv('WHATSAPP_API_KEY')  # Your 7-digit key
PHONE_NUMBER = os.getenv('PHONE_NUMBER')          # e.g., +85291234567
HKD_PORTFOLIO = int(os.getenv('HKD_PORTFOLIO', '3300000'))  # Default 3.3M
HKD_TO_USD = 7.8
PORTFOLIO_USD = HKD_PORTFOLIO / HKD_TO_USD
RISK_USD = PORTFOLIO_USD * 0.005  # 0.5% risk

def send_whatsapp(message):
    if not WHATSAPP_API_KEY or not PHONE_NUMBER:
        print("Missing WhatsApp config – skipping send")
        return
    url = "https://api.callmebot.com/whatsapp.php"
    params = {
        "phone": PHONE_NUMBER,
        "text": message,
        "apikey": WHATSAPP_API_KEY
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            print("WhatsApp sent successfully!")
        else:
            print(f"WhatsApp error: {response.status_code}")
    except Exception as e:
        print(f"WhatsApp failed: {e}")

def run_screen():
    print(f"Running Minervini screen... {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # Get full US tickers (Nasdaq + NYSE)
    try:
        nasdaq_url = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/us_stock_symbols/nasdaq_full_tickers.csv"
        nyse_url = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/us_stock_symbols/nyse_full_tickers.csv"
        nasdaq = pd.read_csv(nasdaq_url)['Symbol'].tolist()
        nyse = pd.read_csv(nyse_url)['Symbol'].tolist()
        tickers = [t for t in nasdaq + nyse if isinstance(t, str)][:1000]  # Limit to 1000 for speed; remove for full
    except:
        print("Ticker list failed – using sample")
        tickers = ['AAPL', 'MSFT', 'GOOGL', 'APGE', 'ZYME', 'INDV', 'ARQT']  # Fallback

    results = []
    for t in tickers:
        try:
            info = yf.Ticker(t).info
            price = info.get('regularMarketPrice') or info.get('previousClose')
            if not price or price < 10: continue
            vol = info.get('averageVolume', 0)
            if vol < 300000: continue

            df = yf.Ticker(t).history(period="15mo")
            if len(df) < 200: continue

            sma50 = df['Close'].rolling(50).mean().iloc[-1]
            sma200 = df['Close'].rolling(200).mean().iloc[-1]
            if not (price > sma50 > sma200): continue

            # Relative Strength vs SPY (YTD outperformance)
            spy_df = yf.Ticker("SPY").history(period="1y")
            spy_ret = (spy_df['Close'].iloc[-1] / spy_df['Close'].iloc[0]) - 1 if len(spy_df) > 0 else 0
            stock_ret = (df['Close'].iloc[-1] / df['Close'].iloc[-252]) - 1 if len(df) > 252 else 0
            if stock_ret < spy_ret * 1.3: continue  # At least 30% better than SPY

            # Buy Point: Recent high + small buffer
            buy_point = round(df['High'][-30:].max() * 1.005, 2)
            if buy_point <= price: continue

            # Stop Loss: Swing low or 50-day SMA -2%
            stop = round(max(df['Low'][-20:].min(), sma50 * 0.98), 2)
            risk_pct = round((buy_point - stop) / buy_point * 100, 1)
            if risk_pct > 12: continue  # Too wide risk

            shares = math.floor(RISK_USD / (buy_point - stop))
            if shares < 20: continue

            results.append({
                'Tick': t,
                'Price': f"{price:.2f}",
                'BuyPoint': f"{buy_point:.2f}",
                'StopLoss': f"{stop:.2f}",
                'Risk%': f"{risk_pct}%",
                'Shares': shares,
                'CapitalUSD': f"${shares * buy_point:,.0f}"
            })
        except Exception as e:
            print(f"Error on {t}: {e}")
            continue
        time.sleep(0.1)  # Rate limit

    # Sort by tightest risk, top 10
    results = sorted(results, key=lambda x: float(x['Risk%'][:-1]))[:10]
    return pd.DataFrame(results)

# Daily job at 00:25 UTC (8:25 AM HK time)
def daily_job():
    df = run_screen()
    date_str = datetime.now().strftime("%d %b %Y")
    count = len(df)
    
    if df.empty:
        msg = f"MINERVINI SCAN – {date_str}\nNo high-quality breakouts today.\n\nYour account: HKD {HKD_PORTFOLIO:,} → 0.5% risk per trade\nRun at {datetime.now().strftime('%H:%M')} HK time"
    else:
        msg = f"MINERVINI BREAKOUTS – {date_str}\n{count} new high-conviction setups found\n\n"
        msg += df.to_string(index=False, justify='center')
        msg += f"\n\nYour account: HKD {HKD_PORTFOLIO:,} → 0.5% risk per trade\nRun at {datetime.now().strftime('%H:%M')} HK time | Cloud server"
    
    send_whatsapp(msg)
    print(f"Scan complete: {count} setups sent")

# Schedule (runs once on start, then daily)
schedule.every().day.at("00:25").do(daily_job)

if __name__ == "__main__":
    print("Minervini Bot started on Render!")
    daily_job()  # Run once on deploy for testing
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute
