import os
from dotenv import load_dotenv
from alpaca_trade_api.rest import REST, TimeFrame
from flask import Flask, render_template_string
import pandas as pd
import ta  # Technical Analysis library

# Load API keys
load_dotenv()

API_KEY = os.getenv("APCA_API_KEY_ID", "")
SECRET_KEY = os.getenv("APCA_API_SECRET_KEY", "")
BASE_URL = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets/v2")

if not API_KEY or not SECRET_KEY:
    raise ValueError("Missing Alpaca API credentials or base URL!")

# Alpaca client
api = REST(API_KEY, SECRET_KEY, BASE_URL)

# Flask app
app = Flask(__name__)

# Simple HTML template
TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Trading Dashboard</title>
    <style>
        body { font-family: Arial; margin: 40px; }
        h1 { color: #333; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ccc; padding: 8px; text-align: center; }
        th { background-color: #f4f4f4; }
    </style>
</head>
<body>
    <h1>Trading Signals</h1>
    <table>
        <tr>
            <th>Symbol</th>
            <th>RSI</th>
            <th>MACD</th>
            <th>MA Signal</th>
            <th>Final Signal</th>
        </tr>
        {% for row in data %}
        <tr>
            <td>{{ row.symbol }}</td>
            <td>{{ row.rsi }}</td>
            <td>{{ row.macd }}</td>
            <td>{{ row.ma_signal }}</td>
            <td><strong>{{ row.final_signal }}</strong></td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

# Helper: Generate trading signals based on RSI, MACD, MA
def analyze_stock(symbol):
    try:
        bars = api.get_bars(symbol, TimeFrame.Day, limit=50).df
        bars.index = pd.to_datetime(bars.index)
        df = bars[['close']].copy()

        # Add TA indicators
        df['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi()
        macd = ta.trend.MACD(df['close'])
        df['macd'] = macd.macd_diff()
        df['ma10'] = df['close'].rolling(window=10).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()

        latest = df.iloc[-1]
        ma_signal = "BUY" if latest['ma10'] > latest['ma20'] else "SELL" if latest['ma10'] < latest['ma20'] else "HOLD"
        rsi_signal = "BUY" if latest['rsi'] < 30 else "SELL" if latest['rsi'] > 70 else "HOLD"
        macd_signal = "BUY" if latest['macd'] > 0 else "SELL" if latest['macd'] < 0 else "HOLD"

        # Combine signals
        final_signal = max([ma_signal, rsi_signal, macd_signal], key=["SELL", "HOLD", "BUY"].index)

        return {
            "symbol": symbol,
            "rsi": round(latest['rsi'], 2),
            "macd": round(latest['macd'], 4),
            "ma_signal": ma_signal,
            "final_signal": final_signal
        }
    except Exception as e:
        return {"symbol": symbol, "rsi": "-", "macd": "-", "ma_signal": "ERROR", "final_signal": str(e)}

@app.route("/")
def dashboard():
    symbols = ["AAPL", "MSFT", "TSLA", "AMZN"]
    data = [analyze_stock(sym) for sym in symbols]
    return render_template_string(TEMPLATE, data=data)

if __name__ == "__main__":
    app.run(debug=False)
