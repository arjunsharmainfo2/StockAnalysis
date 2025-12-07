import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt
import requests
import pandas as pd
import os

# Set your Alpha Vantage API key here
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")

st.set_page_config(layout="wide")
st.title("📈 AI Stock Bot Dashboard")

# --------- SECTOR PERFORMANCE BLOCK ---------
st.header("📊 Sector Performance (Real-Time from Alpha Vantage)")

@st.cache_data(ttl=3600)
def get_sector_performance():
    url = f"https://www.alphavantage.co/query?function=SECTOR&apikey={ALPHA_VANTAGE_API_KEY}"
    response = requests.get(url)
    data = response.json()

    # Parse "Rank A: Real-Time Performance"
    realtime_data = data.get("Rank A: Real-Time Performance", {})
    df = pd.DataFrame(realtime_data.items(), columns=["Sector", "Performance"])
    df["Performance"] = df["Performance"].str.replace('%', '').astype(float)
    return df.sort_values("Performance", ascending=False)

try:
    df_sector = get_sector_performance()
    st.dataframe(df_sector, use_container_width=True)

    # Plotting
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(df_sector["Sector"], df_sector["Performance"])
    ax.set_xlabel("Performance (%)")
    ax.set_title("Real-Time Sector Performance")
    st.pyplot(fig)

except Exception as e:
    st.error(f"Could not load sector data: {e}")

# --------- STOCK TRACKER BLOCK ---------
st.header("📍 Track Individual Stocks with Signals")

tickers = st.multiselect("Enter ticker(s):", ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"], default=["AAPL"])

def get_signals(df):
    df["MA20"] = df["Close"].rolling(window=20).mean()
    df["MA50"] = df["Close"].rolling(window=50).mean()
    df["Signal"] = 0
    df.loc[df["MA20"] > df["MA50"], "Signal"] = 1  # Buy
    df.loc[df["MA20"] < df["MA50"], "Signal"] = -1 # Sell
    return df

for ticker in tickers:
    st.subheader(f"{ticker} — Trend & Signal")
    df = yf.download(ticker, period="30d", interval="1h")

    if df.empty or len(df) < 50:
        st.warning(f"Not enough data for {ticker}")
        continue

    df = get_signals(df)

    # Determine latest signal
    latest_signal = df["Signal"].iloc[-1]
    if latest_signal == 1:
        st.success(f"📈 Signal for {ticker}: **BUY**")
    elif latest_signal == -1:
        st.error(f"📉 Signal for {ticker}: **SELL**")
    else:
        st.info(f"➖ Signal for {ticker}: **HOLD**")

    # Plot chart
    fig, ax = plt.subplots()
    ax.plot(df.index, df["Close"], label="Close Price", alpha=0.6)
    ax.plot(df.index, df["MA20"], label="MA20", linestyle="--")
    ax.plot(df.index, df["MA50"], label="MA50", linestyle="--")

    # Plot buy/sell points
    buy_signals = df[df["Signal"] == 1]
    sell_signals = df[df["Signal"] == -1]
    ax.scatter(buy_signals.index, buy_signals["Close"], marker="^", color="green", label="Buy", s=60)
    ax.scatter(sell_signals.index, sell_signals["Close"], marker="v", color="red", label="Sell", s=60)

    ax.set_title(f"{ticker} - Signals")
    ax.set_ylabel("Price")
    ax.legend()
    st.pyplot(fig)