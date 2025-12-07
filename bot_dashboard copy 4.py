import streamlit as st
import yfinance as yf
from alpaca_trade_api.rest import REST, TimeFrame
import pandas as pd
import os

# Alpaca API credentials - load from env
API_KEY = os.getenv("APCA_API_KEY_ID", "")
API_SECRET = os.getenv("APCA_API_SECRET_KEY", "")
BASE_URL = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets/")

api = REST(API_KEY, API_SECRET, BASE_URL)


st.title("Trading Bot Dashboard")

assets = api.list_assets(status='active')

tickers = [a.symbol for a in assets if a.exchange == 'NASDAQ']

decisions = []


for symbol in tickers:
    try:
        df = yf.download(symbol, period="1mo", interval="1d")
        if df.empty or len(df) < 20:
            continue

        df['ma10'] = df['Close'].rolling(window=10).mean()
        df['ma20'] = df['Close'].rolling(window=20).mean()

        latest = df.iloc[-1]

        if latest['ma10'] > latest['ma20']:
            action = 'BUY'
        elif latest['ma10'] < latest['ma20']:
            action = 'SELL'
        else:
            action = 'HOLD'

        decisions.append({
            'Symbol': symbol,
            'Close': round(latest['Close'], 2),
            'MA10': round(latest['ma10'], 2),
            'MA20': round(latest['ma20'], 2),
            'Decision': action
        })

    except Exception as e:
        print(f"Error processing {symbol}: {e}")

# Convert to DataFrame
result_df = pd.DataFrame(decisions)
print(result_df)



symbols = st.multiselect("Select stocks to track", [a.symbol for a in assets if a.exchange == 'NASDAQ'], default=["MSFT"])

qty = st.number_input("Order quantity", min_value=1, value=1)

def get_data(symbol):
    bars = api.get_bars(symbol, TimeFrame.Hour, limit=50).df
    bars.index = pd.to_datetime(bars.index)
    bars.columns = bars.columns.str.lower()  # lowercase all column names
    return bars

def calc_signals(df):
    df['ma10'] = df['close'].rolling(window=5).mean()
    df['ma20'] = df['close'].rolling(window=15).mean()

    latest = df.iloc[-1]
    print(latest)
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
        order = api.submit_order(
            symbol=symbol,
            qty=qty,
            side=side,
            type='market',
            time_in_force='gtc'
        )
        st.success(f"Order placed: {side} {qty} shares of {symbol}")
        return order
    except Exception as e:
        st.error(f"Order failed: {e}")

for symbol in symbols:
    st.header(f"Stock: {symbol}")
    df = get_data(symbol)
    print(df.shape)
    print(df.head())
    df['ma10'] = df['close'].rolling(window=5).mean()
    df['ma20'] = df['close'].rolling(window=15).mean()

    st.line_chart(df[['close', 'ma10', 'ma20']])

    signal = calc_signals(df)
    st.write(f"Signal: **{signal}**")

    position_qty = get_position(symbol)
    st.write(f"Current Position: {position_qty} shares")

    if st.button(f"Execute {signal} for {symbol}"):
        if signal == "BUY" and position_qty == 0:
            place_order(symbol, "buy", qty)
        elif signal == "SELL" and position_qty > 0:
            place_order(symbol, "sell", position_qty)
        else:
            st.info("No action taken based on current position and signal.")