import streamlit as st
from alpaca_trade_api.rest import REST, TimeFrame
import pandas as pd
import time
import os

# --- Alpaca API credentials ---
API_KEY = os.getenv("APCA_API_KEY_ID", "")
API_SECRET = os.getenv("APCA_API_SECRET_KEY", "")
BASE_URL = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets/")
api = REST(API_KEY, API_SECRET, BASE_URL)

st.title("NASDAQ Trading Bot Dashboard")

# --- Functions ---
def get_data(symbol, limit=200):
    try:
        bars = api.get_bars(symbol, TimeFrame.Minute, limit=limit).df
        if bars.empty:
            return bars
        bars.index = pd.to_datetime(bars.index)
        bars.columns = bars.columns.str.lower()
        return bars
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return pd.DataFrame()

def calc_signals(df, short_window=10, long_window=20):
    df['ma10'] = df['close'].rolling(window=short_window).mean()
    df['ma20'] = df['close'].rolling(window=long_window).mean()
    st.write(df[['close', 'ma10', 'ma20']].tail(10))
    st.write(f"{symbol} dataframe length: {len(df)}")
    st.write(df.tail(5))
    latest = df.iloc[-1]
    st.write("Latest MA10:", latest['ma10'])
    st.write("Latest MA20:", latest['ma20'])
    if latest['ma10'] > latest['ma20']:
        return "BUY"
    elif latest['ma10'] < latest['ma20']:
        return "SELL"
    else:
        return "HOLD"

def get_position(symbol):
    try:
        pos = api.get_position(symbol)
        return int(pos.qty)
    except:
        return 0

def place_order(symbol, side, qty):
    try:
        api.submit_order(
            symbol=symbol,
            qty=qty,
            side=side,
            type='market',
            time_in_force='gtc'
        )
        st.success(f"Order executed: {side.upper()} {qty} shares of {symbol}")
    except Exception as e:
        st.error(f"Order failed: {e}")

# --- Sidebar settings ---
batch_size = st.sidebar.number_input("Batch size for API requests", min_value=10, max_value=100, value=50)
refresh_interval = st.sidebar.number_input("Refresh interval (seconds)", min_value=30, max_value=3600, value=300)
default_qty = st.sidebar.number_input("Default order quantity", min_value=1, value=1)
auto_trade = st.sidebar.checkbox("Enable Auto Trade (based on signals)", value=False)

# --- Get tradable NASDAQ symbols ---
assets = api.list_assets(status='active')
tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
# tickers = [a.symbol for a in assets if a.exchange == 'NASDAQ' and a.tradable]
st.write(tickers)

# --- 3-column Signal Overview ---
buy_list, sell_list, hold_list = [], [], []

for symbol in tickers[:50]:  # fetch top 50 to start
    df = get_data(symbol)
    if df.empty or len(df) < 20:
        st.warning(f"Not enough data for {symbol}")
        continue  # this is now valid
    signal = calc_signals(df)
    if signal == "BUY":
        buy_list.append(symbol)
    elif signal == "SELL":
        sell_list.append(symbol)
    else:
        hold_list.append(symbol)
    time.sleep(0.2)

st.subheader("Stock Signals Overview")
col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("BUY")
    for s in buy_list:
        st.write(s)
with col2:
    st.subheader("SELL")
    for s in sell_list:
        st.write(s)
with col3:
    st.subheader("HOLD")
    for s in hold_list:
        st.write(s)

# --- Live Stock Tracker ---
st.subheader("Live Stock Tracker (Manual & Auto Trading)")
symbols = st.multiselect("Select stocks to track live", tickers, default=["MSFT"])

for symbol in symbols:
    st.header(f"Stock: {symbol}")
    df = get_data(symbol)
    if df.empty:
        st.warning("No data available.")
        continue

    signal = calc_signals(df)
    st.line_chart(df[['close', 'ma10', 'ma20']])
    st.write(f"Current Signal: **{signal}**")

    position_qty = get_position(symbol)
    st.write(f"Current Position: {position_qty} shares")

    # Manual trade buttons
    col_buy, col_sell = st.columns(2)
    with col_buy:
        if st.button(f"BUY {default_qty} shares of {symbol}"):
            place_order(symbol, "buy", default_qty)
    with col_sell:
        if st.button(f"SELL {default_qty} shares of {symbol}"):
            place_order(symbol, "sell", default_qty)

    # Auto Trade
    if auto_trade:
        if signal == "BUY" and position_qty == 0:
            place_order(symbol, "buy", default_qty)
        elif signal == "SELL" and position_qty > 0:
            place_order(symbol, "sell", position_qty)
