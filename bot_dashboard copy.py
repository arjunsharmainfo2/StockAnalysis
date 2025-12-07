import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from alpaca_trade_api.rest import REST
import os

# Alpaca Configuration
API_KEY = os.getenv("APCA_API_KEY_ID", "")
API_SECRET = os.getenv("APCA_API_SECRET_KEY", "")
BASE_URL = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets/v2")  # Use paper trading endpoint

alpaca = REST(API_KEY, API_SECRET, BASE_URL)

# Stock Settings
tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN']
window_sma_short = 10
window_sma_long = 30
trade_qty = 1

def fetch_signals(ticker):
    df = yf.download(ticker, period='3mo', interval='1d')
    df['SMA10'] = df['Close'].rolling(window=window_sma_short).mean()
    df['SMA30'] = df['Close'].rolling(window=window_sma_long).mean()

    delta = df['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    signal = "HOLD"
    if (latest['SMA10'] > latest['SMA30']) and (prev['SMA10'] <= prev['SMA30']) and (latest['RSI'] < 30):
        signal = "BUY"
    elif (latest['SMA10'] < latest['SMA30']) and (prev['SMA10'] >= prev['SMA30']) and (latest['RSI'] > 70):
        signal = "SELL"
    return df, signal

def place_trade(ticker, signal):
    try:
        if signal == "BUY":
            alpaca.submit_order(symbol=ticker, qty=trade_qty, side='buy', type='market', time_in_force='gtc')
            return f"✅ BUY order placed for {ticker}"
        elif signal == "SELL":
            alpaca.submit_order(symbol=ticker, qty=trade_qty, side='sell', type='market', time_in_force='gtc')
            return f"✅ SELL order placed for {ticker}"
        else:
            return "No trade executed"
    except Exception as e:
        return f"⚠️ Trade failed: {e}"

# Streamlit App
st.set_page_config(page_title="AI Stock Bot", layout="wide")
st.title("📈 AI Stock Bot Dashboard with Live Trading (Alpaca)")
st.markdown("Tracking and trading US stocks using SMA crossover and RSI strategy")

for ticker in tickers:
    st.subheader(f"📊 {ticker}")
    data, signal = fetch_signals(ticker)
    st.write(f"**Signal:** {signal}")

    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot(data['Close'], label='Close', alpha=0.6)
    ax.plot(data['SMA10'], label='SMA10', linestyle='--')
    ax.plot(data['SMA30'], label='SMA30', linestyle='--')
    ax.set_title(f"{ticker} Price & SMA")
    ax.legend()
    st.pyplot(fig)

    if st.button(f"Execute {signal} for {ticker}", key=ticker):
        result = place_trade(ticker, signal)
        st.success(result)