# main.py — Top 5 ATH + SMA + Volume in USD (WhatsApp test)
import os
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime
import time
from zoneinfo import ZoneInfo

hk_tz = ZoneInfo("Asia/Hong_Kong")
def now_hk(): return datetime.now(hk_tz).strftime("%d %b %Y %H:%M HK")

WHATSAPP_API_KEY = os.getenv('WHATSAPP_API_KEY')
PHONE_NUMBER     = os.getenv('PHONE_NUMBER')

def send_whatsapp(msg):
    if not WHATSAPP_API_KEY or not PHONE_NUMBER:
        print("WhatsApp config missing")
        return
    try:
        requests.get("https://api.callmebot.com/whatsapp.php",
                     params={"phone": PHONE_NUMBER, "text": msg, "apikey": WHATSAPP_API_KEY}, timeout=15)
        print("WhatsApp sent")
    except Exception as e:
        print(f"WhatsApp failed: {e}")

# Top ~200 largest US stocks (covers way beyond top 5)
TOP_TICKERS = [
    "AAPL","MSFT","NVDA","GOOGL","AMZN","META","BRK.B","TSLA","LLY","AVGO",
    "JPM","V","WMT","UNH","XOM","MA","PG","JNJ","HD","ORCL","MRK","COST","ABBV","BAC","CRM",
    "NFLX","AMD","KO","ADBE","PEP","QCOM","TMO","LIN","WFC","CSCO","MCD","INTC","ABT","DIS",
    "VZ","AMGN","PFE","CMCSA","NKE","TXN","PM","IBM","GE","HON","UNP","RTX","SPGI","CAT",
    "NEE","GS","MS","LOW","BKNG","BLK","AXP","SYK","ELV","TJX","LMT","PLD","MDT","PGR","CB",
    "ADP","ETN","REGN","VRTX","ISRG","SBUX","BA","AMAT","BMY","DE","GILD","LRCX","ADI","MMC",
    "CI","MU","SCHW","SO","MO","TMUS","DUK","ZTS","BDX","KLAC","CL","ICE","SHW","ITW","TGT",
    "BSX","EOG","CME","MCK","FDX","APH","TT","GD","CVS","CSX","EMR","NOC","PNC","HUM","CDNS",
    "RSG","MSI","CTAS","PCAR","MAR","ROP","ORLY","AFL","AZN","WELL","OXY","GM","CARR","CPRT",
    "MSCI","COF","TFC","TRV","AIG","SPG","PSA","FTNT","DHI","O","GWW","CTVA","NUE","JCI","D","PAYX"
]

def run_test():
    msg = f"*yfinance ATH TEST — {now_hk()}*\nTop 5 US stocks by market cap at ALL-TIME HIGH\n\n"
    results = []

    for ticker in TOP_TICKERS:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="2y", auto_adjust=False)   # raw prices
            if len(hist) < 250: continue

            close = hist['Close'].iloc[-1]
            high_all = hist['High'].max()
            ath = hist['High'][:-1].max()   # previous all-time high

            # Must close at or above previous ATH
            if close < ath: continue

            market_cap = t.info.get('marketCap', 0)
            if not market_cap: continue

            sma50  = hist['Close'].rolling(50).mean().iloc[-1]
            sma200 = hist['Close'].rolling(200).mean().iloc[-1]

            latest_vol_shares = hist['Volume'].iloc[-1]
