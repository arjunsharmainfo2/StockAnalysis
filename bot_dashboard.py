import os
import streamlit as st
from alpaca_trade_api.rest import REST, TimeFrame
import pandas as pd
import time
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
from investment_finder import InvestmentFinderSystem

# Simple keyword-based sentiment dictionaries for news headlines
POS_WORDS = {"beat", "surge", "rise", "record", "profit", "gain", "upgrade", "outperform", "strong", "growth", "tops"}
NEG_WORDS = {"miss", "fall", "drop", "loss", "cut", "downgrade", "lawsuit", "probe", "weak", "slump", "fraud"}

# ------------------------------
# Alpaca API credentials
# ------------------------------
API_KEY = os.getenv("APCA_API_KEY_ID", "")
API_SECRET = os.getenv("APCA_API_SECRET_KEY", "")
BASE_URL = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets/")
api = REST(API_KEY, API_SECRET, BASE_URL) if API_KEY and API_SECRET else None


@st.cache_data(ttl=600)
def fetch_assets():
    # Pull active US equities and group by exchange for lightweight categorization
    if api is None:
        return [], {}
    assets = api.list_assets(status="active", asset_class="us_equity")
    t2c = {}
    syms = []
    for a in assets:
        if not a.tradable:
            continue
        cat = f"Exchange: {getattr(a, 'exchange', 'Unknown')}"
        t2c[a.symbol] = cat
        syms.append(a.symbol)
    unique_syms = sorted(set(syms))
    return unique_syms, t2c


all_tickers, ticker_to_category = fetch_assets()
all_categories = sorted(list(set(ticker_to_category.values())))

st.title("Trading Bot Dashboard")

if not API_KEY or not API_SECRET:
    st.error("🔐 Alpaca API credentials not set. Viewing data-only mode. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in environment/Streamlit secrets to enable live data and trading.")
    st.info("💡 To set environment variables: export APCA_API_KEY_ID='your_key' and export APCA_API_SECRET_KEY='your_secret'")
else:
    st.success(f"✅ Connected to Alpaca API: {BASE_URL}")

# --- Auto-Trade Universe Selection and Controls ---
st.subheader("Ticker Selection")

# Simple comma-separated ticker input
ticker_input = st.text_input(
    "Enter tickers (comma-separated)",
    value="AAPL, MSFT, GOOGL, AMZN, TSLA",
    help="e.g., AAPL, MSFT, GOOGL"
)

# Parse and validate tickers
if ticker_input:
    tickers_for_trade = [s.strip().upper() for s in ticker_input.split(',') if s.strip()]
else:
    tickers_for_trade = []

original_tickers = list(tickers_for_trade)

st.caption(f"**{len(tickers_for_trade)}** symbols selected for trading.")

# --- Volatility Filter (ATR-based) ---
st.markdown("---")
st.subheader("Volatility Filter (Optional)")
st.caption("Filter stocks by Average True Range (ATR) to remove excessively volatile tickers.")

use_volatility_filter = st.checkbox("Apply ATR Volatility Filter", value=False)
volatility_threshold = st.slider(
    "Max ATR as % of Price (volatility threshold)",
    min_value=1,
    max_value=20,
    value=5,
    step=1,
    help="Remove stocks where ATR > this % of current price"
)

filtered_by_volatility = tickers_for_trade
if use_volatility_filter and tickers_for_trade:
    with st.spinner("Filtering by volatility (ATR)..."):
        try:
            if not API_KEY or not API_SECRET:
                raise ValueError("Missing Alpaca API credentials for volatility filter.")
            finder = InvestmentFinderSystem(
                api_key=API_KEY,
                api_secret=API_SECRET,
                base_url=BASE_URL,
                tickers_universe=tickers_for_trade,
                short_ma=10,
                long_ma=20
            )
            filtered_by_volatility, atr_ratios = finder.filter_universe(volatility_threshold=volatility_threshold / 100)
            
            # Display ATR summary
            st.success(f"✅ Volatility filter applied: {len(filtered_by_volatility)}/{len(tickers_for_trade)} stocks passed")
            with st.expander("View ATR Analysis Details"):
                atr_df = finder.get_atr_summary_df()
                st.dataframe(atr_df, use_container_width=True)
        except Exception as e:
            st.error(f"Error during volatility filtering: {e}")
            filtered_by_volatility = tickers_for_trade

    if not filtered_by_volatility:
        st.warning("All tickers were filtered out by the ATR threshold. Using the original list instead.")
        filtered_by_volatility = original_tickers

# Update trading universe
tickers_for_trade = filtered_by_volatility

st.markdown("---")

# Auto-Trade toggle
auto_trade = st.checkbox("Enable Auto-Trade for selected stocks")
refresh_interval = st.number_input("Auto-Trade interval (minutes)", min_value=1, value=5)

# --- Manual Trade Button ---
run_manual_trade = st.button("Run Manual Trade Check & Execute")
st.markdown("---")

# ------------------------------
# Yahoo Finance Analysis Functions
# ------------------------------
@st.cache_data(ttl=600)
def get_yahoo_week_data(symbol):
    """Fetch 1-week historical data from Yahoo Finance with technical indicators."""
    try:
        ticker = yf.Ticker(symbol)
        # Get 1 week of data (5 trading days) with 1-day interval
        hist = ticker.history(period="1mo", interval="1d")
        
        if hist.empty:
            return None
        
        # Calculate technical indicators
        hist['MA5'] = hist['Close'].rolling(window=5).mean()
        hist['MA10'] = hist['Close'].rolling(window=10).mean()
        hist['MA20'] = hist['Close'].rolling(window=20).mean()
        
        # Calculate RSI
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        hist['RSI'] = 100 - (100 / (1 + rs))
        
        # Volume analysis
        hist['Volume_MA'] = hist['Volume'].rolling(window=5).mean()
        
        return hist
    except Exception as e:
        st.error(f"❌ Error fetching Yahoo 1-week data for {symbol}: {e}")
        return None

@st.cache_data(ttl=600)
def get_yahoo_analysis(symbol):
    """Fetches price info and basic data from Yahoo Finance. Cached for 10 minutes."""
    try:
        ticker = yf.Ticker(symbol)
        
        # Get basic info (more reliable than recommendations/news)
        info = ticker.info
        pe_ratio = info.get('trailingPE', 'N/A')
        market_cap = info.get('marketCap', 'N/A')
        fifty_two_week_high = info.get('fiftyTwoWeekHigh', 'N/A')
        fifty_two_week_low = info.get('fiftyTwoWeekLow', 'N/A')
        current_price = info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))
        
        summary = f"PE: {pe_ratio} | 52W High: ${fifty_two_week_high} | 52W Low: ${fifty_two_week_low}"
        
        return {
            "Summary": summary,
            "Market Cap": f"${market_cap:,.0f}" if isinstance(market_cap, (int, float)) else market_cap,
            "Current Price": current_price
        }
    except Exception as e:
        st.warning(f"⚠️ Yahoo Finance data unavailable for {symbol}: {e}")
        return {
            "Summary": "Data unavailable",
            "Market Cap": "N/A",
            "Current Price": "N/A"
        }


# ------------------------------
# News sentiment helpers
# ------------------------------

def _score_headline(text: str) -> int:
    t = text.lower()
    pos = sum(1 for w in POS_WORDS if w in t)
    neg = sum(1 for w in NEG_WORDS if w in t)
    return pos - neg  # >0 bullish, <0 bearish


@st.cache_data(ttl=600)
def get_news_signal(symbol, limit=20):
    """Fetch Yahoo Finance news and derive a simple BUY/SELL/HOLD signal from headlines."""
    try:
        ticker = yf.Ticker(symbol)
        news_items = []
        attr_news = getattr(ticker, "news", None)
        if isinstance(attr_news, list):
            news_items = attr_news
        if not news_items and hasattr(ticker, "get_news"):
            try:
                fetched = ticker.get_news()
                if isinstance(fetched, list):
                    news_items = fetched
            except Exception as e:
                print(f"{symbol} get_news error: {e}")
                st.info(f"ℹ️ No news available via get_news() for {symbol}")
        news_items = news_items[:limit] if news_items else []
    except Exception as e:
        print(f"{symbol} news fetch error: {e}")
        st.warning(f"⚠️ Could not fetch news for {symbol}: {e}")
        news_items = []

    scores = []
    headlines = []
    news_details = []
    
    for item in news_items:
        title = item.get("title") or ""
        if not title:
            continue
        
        # Extract full news details
        link = item.get("link", "")
        publisher = item.get("publisher", "Unknown")
        published_time = item.get("providerPublishTime", "")
        
        headlines.append(title)
        news_details.append({
            "title": title,
            "publisher": publisher,
            "link": link,
            "time": pd.to_datetime(published_time, unit='s').strftime('%Y-%m-%d %H:%M') if published_time else "N/A"
        })
        scores.append(_score_headline(title))

    if not scores:
        return {"symbol": symbol, "news_signal": "HOLD", "news_score": 0.0, "headlines": [], "news_details": [], "empty": True}

    avg = sum(scores) / len(scores)
    if avg > 0.5:
        signal = "BUY"
    elif avg < -0.5:
        signal = "SELL"
    else:
        signal = "HOLD"

    return {
        "symbol": symbol,
        "news_signal": signal,
        "news_score": round(avg, 2),
        "headlines": headlines[:5],
        "news_details": news_details[:10],  # Return top 10 news items with full details
        "empty": False,
    }

# ------------------------------
# 1-Week Analysis with Yahoo Finance
# ------------------------------
st.subheader("📊 1-Week Stock Analysis & Trading Signals")

# Use the same tickers from main input for analysis
selected_symbols = tickers_for_trade if tickers_for_trade else []
st.caption(f"Analyzing {len(selected_symbols)} tickers using Yahoo Finance 1-week data + news sentiment")


# --- Comprehensive 1-week analysis function ---
@st.cache_data(ttl=300)
def analyze_stock_1week(symbol):
    """
    Comprehensive 1-week analysis combining:
    - Yahoo Finance 1-week price data and technical indicators
    - News sentiment analysis
    - Buy/Sell recommendation
    """
    # Get 1-week data from Yahoo Finance
    week_data = get_yahoo_week_data(symbol)
    
    if week_data is None or len(week_data) < 5:
        return {
            "Symbol": symbol,
            "Signal": "NO DATA",
            "Price": "N/A",
            "Week_Change_%": 0,
            "RSI": "N/A",
            "Recommendation": "INSUFFICIENT DATA"
        }
    
    # Get the last 5 trading days
    recent_data = week_data.tail(7)
    latest = recent_data.iloc[-1]
    week_start = recent_data.iloc[0]
    
    # Calculate metrics
    current_price = latest['Close']
    week_change_pct = ((current_price - week_start['Close']) / week_start['Close']) * 100
    
    ma5 = latest.get('MA5', None)
    ma10 = latest.get('MA10', None)
    rsi = latest.get('RSI', None)
    volume_ratio = latest['Volume'] / latest.get('Volume_MA', 1) if latest.get('Volume_MA', 0) > 0 else 1
    
    # Get news sentiment
    news_data = get_news_signal(symbol)
    news_signal = news_data.get('news_signal', 'HOLD')
    news_score = news_data.get('news_score', 0)
    
    # Technical signal generation
    tech_signal = "HOLD"
    tech_strength = 0
    reasons = []
    
    # MA crossover analysis
    if pd.notna(ma5) and pd.notna(ma10):
        if ma5 > ma10 and current_price > ma5:
            tech_signal = "BUY"
            tech_strength += 2
            reasons.append("MA5 > MA10 with price above MA5")
        elif ma5 < ma10 and current_price < ma5:
            tech_signal = "SELL"
            tech_strength -= 2
            reasons.append("MA5 < MA10 with price below MA5")
    
    # RSI analysis
    if pd.notna(rsi):
        if rsi < 30:
            tech_strength += 1
            reasons.append(f"RSI oversold ({rsi:.1f})")
            if tech_signal != "SELL":
                tech_signal = "BUY"
        elif rsi > 70:
            tech_strength -= 1
            reasons.append(f"RSI overbought ({rsi:.1f})")
            if tech_signal != "BUY":
                tech_signal = "SELL"
    
    # Volume confirmation
    if volume_ratio > 1.5:
        tech_strength += 1 if tech_signal == "BUY" else -1
        reasons.append(f"High volume ({volume_ratio:.1f}x avg)")
    
    # Week trend
    if week_change_pct > 3:
        tech_strength += 1
        reasons.append(f"Strong uptrend (+{week_change_pct:.1f}%)")
    elif week_change_pct < -3:
        tech_strength -= 1
        reasons.append(f"Strong downtrend ({week_change_pct:.1f}%)")
    
    # Combine technical + news sentiment for final recommendation
    final_signal = tech_signal
    confidence = "MEDIUM"
    
    if tech_signal == "BUY" and news_signal == "BUY":
        final_signal = "STRONG BUY"
        confidence = "HIGH"
    elif tech_signal == "SELL" and news_signal == "SELL":
        final_signal = "STRONG SELL"
        confidence = "HIGH"
    elif tech_signal == "BUY" and news_signal == "SELL":
        final_signal = "HOLD"
        confidence = "LOW"
        reasons.append("Mixed signals: Tech=BUY, News=SELL")
    elif tech_signal == "SELL" and news_signal == "BUY":
        final_signal = "HOLD"
        confidence = "LOW"
        reasons.append("Mixed signals: Tech=SELL, News=BUY")
    
    return {
        "Symbol": symbol,
        "Price": f"${current_price:.2f}",
        "Week_Change_%": round(week_change_pct, 2),
        "MA5": round(ma5, 2) if pd.notna(ma5) else "N/A",
        "MA10": round(ma10, 2) if pd.notna(ma10) else "N/A",
        "RSI": round(rsi, 1) if pd.notna(rsi) else "N/A",
        "Volume_Ratio": round(volume_ratio, 2),
        "Tech_Signal": tech_signal,
        "News_Signal": news_signal,
        "News_Score": news_score,
        "Final_Signal": final_signal,
        "Confidence": confidence,
        "Reasons": " | ".join(reasons) if reasons else "Neutral market conditions",
        "week_data": recent_data,
        "news_details": news_data.get('news_details', [])
    }


# --- Helper functions for data retrieval and plotting ---

@st.cache_data(ttl=600)
def get_trend_data(symbol, _timeframe=TimeFrame.Day, limit=30, ma1=10, ma2=20):
    """Fetches bar data and calculates MAs for trend analysis. Cached for 10 minutes.
    Note: _timeframe is excluded from cache hash (prefixed with underscore)."""
    if api is None:
        # Try Yahoo Finance as fallback
        week_data = get_yahoo_week_data(symbol)
        if week_data is not None:
            # Normalize column names to lowercase for consistency
            week_data.columns = [col.lower() if isinstance(col, str) else col for col in week_data.columns]
            week_data[f"ma{ma1}"] = week_data["close"].rolling(window=ma1).mean()
            week_data[f"ma{ma2}"] = week_data["close"].rolling(window=ma2).mean()
            return week_data
        st.error(f"⚠️ Cannot fetch data for {symbol}: Alpaca API not initialized. Check API credentials.")
        return None
    try:
        df = api.get_bars(symbol, _timeframe, limit=limit).df
        if df.empty:
            # Fallback to Yahoo Finance
            week_data = get_yahoo_week_data(symbol)
            if week_data is not None:
                # Normalize column names to lowercase for consistency
                week_data.columns = [col.lower() if isinstance(col, str) else col for col in week_data.columns]
                week_data[f"ma{ma1}"] = week_data["close"].rolling(window=ma1).mean()
                week_data[f"ma{ma2}"] = week_data["close"].rolling(window=ma2).mean()
                return week_data
            st.warning(f"⚠️ No data returned for {symbol} ({_timeframe})")
            return None
        
        df[f"ma{ma1}"] = df["close"].rolling(window=ma1).mean()
        df[f"ma{ma2}"] = df["close"].rolling(window=ma2).mean()
        return df
    except Exception as e:
        # Fallback to Yahoo Finance
        week_data = get_yahoo_week_data(symbol)
        if week_data is not None:
            # Normalize column names to lowercase for consistency
            week_data.columns = [col.lower() if isinstance(col, str) else col for col in week_data.columns]
            week_data[f"ma{ma1}"] = week_data["close"].rolling(window=ma1).mean()
            week_data[f"ma{ma2}"] = week_data["close"].rolling(window=ma2).mean()
            return week_data
        st.error(f"❌ Error fetching data for {symbol}: {e}")
        print(f"Error fetching data for {symbol}: {e}")
        return None

@st.cache_data(ttl=600)
def analyze_trend(symbol):
    """Generates the trend signal and returns summary metrics. Cached for 10 minutes.
    
    Integrates technical signals (MA crossover) with analyst recommendations:
    - BUY + Strong Buy/Outperform rec → STRONG BUY
    - BUY + Hold/Neutral rec → HOLD
    - SELL only executes if rec is Underperform/Sell, otherwise HOLD
    """
    df = get_trend_data(symbol, _timeframe=TimeFrame.Day, limit=30, ma1=10, ma2=20)
    
    if df is None or len(df) < 20:
        return {"Symbol": symbol, "Signal": "NO DATA"}

    # Data is now normalized to lowercase by get_trend_data
    pct_change = ((df["close"].iloc[-1] / df["close"].iloc[0]) - 1) * 100
    latest = df.iloc[-1]
    
    ma10_val = latest.get("ma10")
    ma20_val = latest.get("ma20")

    # Technical signal from MA crossover
    if pd.isna(ma10_val) or pd.isna(ma20_val):
        tech_signal = "HOLD"
    elif pct_change > 2 and ma10_val > ma20_val:
        tech_signal = "BUY"
    elif pct_change < -2 and ma10_val < ma20_val:
        tech_signal = "SELL"
    else:
        tech_signal = "HOLD"

    # Fetch analyst recommendation
    analyst_data = get_yahoo_analysis(symbol)
    analyst_rec = analyst_data.get("Summary", "").lower()  # e.g., "PE: 25 | ..."
    
    # Integrate analyst recommendation with technical signal
    signal = tech_signal
    if tech_signal == "BUY":
        if "strong buy" in analyst_rec or "outperform" in analyst_rec:
            signal = "STRONG BUY"
        elif "hold" in analyst_rec or "neutral" in analyst_rec:
            signal = "HOLD"
    elif tech_signal == "SELL":
        if "underperform" not in analyst_rec and "sell" not in analyst_rec:
            signal = "HOLD"  # Don't sell unless rec supports it

    news_sig = get_news_signal(symbol)

    return {
        "Symbol": symbol,
        "Category": ticker_to_category.get(symbol, "Uncategorized"),
        "Close": round(latest["close"], 2),
        "1M %": round(pct_change, 2),
        "MA10": round(ma10_val, 2) if not pd.isna(ma10_val) else None,
        "MA20": round(ma20_val, 2) if not pd.isna(ma20_val) else None,
        "Tech Signal": tech_signal,
        "Signal": signal,
        "News Signal": news_sig.get("news_signal"),
        "News Score": news_sig.get("news_score"),
        "News Headlines": news_sig.get("headlines", []),
    }

def plot_analysis(df, symbol, timeframe_label):
    """Generates an interactive Plotly line chart for close, MA10, and MA20."""
    if df is None or df.empty:
        st.warning(f"No data to plot for {symbol}.")
        return

    # Reset index to make timestamp a column for Plotly
    df_plot = df.reset_index()
    
    # Create figure
    fig = go.Figure()
    
    # Add Close Price trace
    fig.add_trace(go.Scatter(
        x=df_plot.index,
        y=df_plot['close'],
        mode='lines',
        name='Close Price',
        line=dict(color='blue', width=2)
    ))
    
    # Add MA10 trace
    if 'ma10' in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=df_plot.index,
            y=df_plot['ma10'],
            mode='lines',
            name='MA10',
            line=dict(color='green', width=1, dash='dash')
        ))
    
    # Add MA20 trace
    if 'ma20' in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=df_plot.index,
            y=df_plot['ma20'],
            mode='lines',
            name='MA20',
            line=dict(color='red', width=1, dash='dash')
        ))
    
    # Update layout
    fig.update_layout(
        title=f'{symbol} Price and Moving Averages ({timeframe_label})',
        xaxis_title='Time',
        yaxis_title='Price (USD)',
        hovermode='x unified',
        height=500,
        template='plotly_white'
    )
    
    # Display the interactive plot in Streamlit
    st.plotly_chart(fig, use_container_width=True)


def calculate_position_size(entry_price, symbol, risk_percent=0.01, max_risk_atr_multiplier=2):
    """Calculate position size based on 14-day ATR and risk % of portfolio.

    qty = (portfolio_equity * risk_percent) / (ATR * max_risk_atr_multiplier)
    where ATR is 14-day Average True Range and acts as the per-share risk proxy.
    """
    try:
        if api is None:
            return 0
        account = api.get_account()
        portfolio_equity = float(getattr(account, "equity", 0))
        if portfolio_equity <= 0 or entry_price <= 0:
            return 0

        risk_cap = portfolio_equity * risk_percent

        bars = api.get_bars(symbol, TimeFrame.Day, limit=30).df
        if bars is None or bars.empty or len(bars) < 15:
            return 0

        high = bars["high"]
        low = bars["low"]
        close = bars["close"]
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()
        atr_val = atr.iloc[-1]

        if pd.isna(atr_val) or atr_val <= 0:
            return 0

        per_share_risk = atr_val * max_risk_atr_multiplier
        if per_share_risk <= 0:
            return 0

        qty = int(risk_cap / per_share_risk)
        return max(qty, 0)
    except Exception as e:
        print(f"{symbol}: error calculating position size -> {e}")
        return 0


def analyze_pnl(trade_log_df):
    """Pair BUY/OPEN entries with subsequent SELLs to derive realized PnL and win rate."""
    if trade_log_df is None or trade_log_df.empty:
        return {
            "realized_pnl": 0.0,
            "win_rate": 0.0,
            "paired_trades": 0,
            "pair_details": pd.DataFrame(),
        }

    df = trade_log_df.copy()
    df.columns = [c.strip().lower() for c in df.columns]

    action_col = None
    for candidate in ("action", "side", "order_type"):
        if candidate in df.columns:
            action_col = candidate
            break

    required_cols = {"symbol", "status", "price"}
    if action_col:
        required_cols.add(action_col)
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Trade log missing required columns: {', '.join(sorted(missing))}")

    qty_col = None
    for candidate in ("qty", "quantity", "shares"):
        if candidate in df.columns:
            qty_col = candidate
            break

    if "timestamp" in df.columns:
        df = df.sort_values("timestamp")
    elif "time" in df.columns:
        df = df.sort_values("time")

    open_buys = {}
    pairs = []

    for _, row in df.iterrows():
        sym = str(row["symbol"]).upper()
        status = str(row.get("status", "")).upper()
        action = str(row[action_col]).upper() if action_col else ""
        try:
            price = float(row["price"])
        except Exception:
            continue

        qty_val = 1.0
        if qty_col and pd.notna(row.get(qty_col)):
            try:
                qty_val = float(row[qty_col])
            except Exception:
                qty_val = 1.0

        if action == "BUY" and status == "OPEN":
            open_buys.setdefault(sym, []).append({"price": price, "qty": qty_val})
            continue

        if action == "SELL" and sym in open_buys and open_buys[sym]:
            sell_qty = qty_val
            sell_price = price

            while sell_qty > 0 and open_buys[sym]:
                buy_trade = open_buys[sym][0]
                matched_qty = min(buy_trade["qty"], sell_qty)
                pnl = (sell_price - buy_trade["price"]) * matched_qty

                pairs.append({
                    "symbol": sym,
                    "buy_price": round(buy_trade["price"], 4),
                    "sell_price": round(sell_price, 4),
                    "qty": matched_qty,
                    "pnl": round(pnl, 2),
                })

                buy_trade["qty"] -= matched_qty
                sell_qty -= matched_qty

                if buy_trade["qty"] <= 0:
                    open_buys[sym].pop(0)
                else:
                    break

    paired_count = len(pairs)
    realized_pnl = round(sum(p["pnl"] for p in pairs), 2)
    wins = sum(1 for p in pairs if p["pnl"] > 0)
    win_rate = round((wins / paired_count) * 100, 2) if paired_count else 0.0

    return {
        "realized_pnl": realized_pnl,
        "win_rate": win_rate,
        "paired_trades": paired_count,
        "pair_details": pd.DataFrame(pairs),
    }

def process_stock(symbol, qty=1):
    # Function to process stock (kept mostly the same, but using the new data getter)
    df = get_trend_data(symbol, _timeframe=TimeFrame.Minute, limit=200, ma1=10, ma2=20)
    
    if df is None or len(df) < 20:
        return f"{symbol}: Not enough minute data"

    latest = df.iloc[-1]
    ma10_val = latest.get("ma10")
    ma20_val = latest.get("ma20")

    if pd.isna(ma10_val) or pd.isna(ma20_val):
        signal = "HOLD"
    elif ma10_val > ma20_val:
        signal = "BUY"
    elif ma10_val < ma20_val:
        signal = "SELL"
    else:
        signal = "HOLD"

    try:
        position_qty = int(api.get_position(symbol).qty) if api is not None else 0
    except:
        position_qty = 0

    # Execute trade if auto_trade
    if auto_trade:
        if signal == "BUY" and position_qty == 0:
            # Determine size via ATR-based risk model (1% portfolio risk, ATR*2 stop proxy)
            entry_price = latest["close"]
            qty_to_trade = calculate_position_size(entry_price, symbol, risk_percent=0.01, max_risk_atr_multiplier=2)
            if qty_to_trade <= 0:
                st.warning(f"{symbol}: position size = 0 (insufficient equity or ATR data). Skipping buy.")
            else:
                stop_loss_price = entry_price * 0.98  # 2% below latest close
                take_profit_price = entry_price * 1.04  # 4% above latest close
                if api is not None:
                    api.submit_order(
                        symbol=symbol,
                        qty=qty_to_trade,
                        side="buy",
                        type="market",
                        time_in_force="gtc",
                        order_class="bracket",
                        take_profit=dict(limit_price=round(take_profit_price, 2)),
                        stop_loss=dict(stop_price=round(stop_loss_price, 2))
                    )
        elif signal == "SELL" and position_qty > 0:
            if api is not None:
                api.submit_order(symbol=symbol, qty=position_qty, side="sell", type="market", time_in_force="gtc")
    
    # Plot minute data - Make it more visible with an option to hide
    st.markdown(f"##### 📊 Minute-Bar Chart for {symbol}")
    df_plot = get_trend_data(symbol, _timeframe=TimeFrame.Minute, limit=200, ma1=10, ma2=20)
    plot_analysis(df_plot, symbol, "200 Min Bars")

    return {
        "Symbol": symbol,
        "Close": round(latest['close'], 2),
        "MA10": round(ma10_val, 2) if not pd.isna(ma10_val) else None,
        "MA20": round(ma20_val, 2) if not pd.isna(ma20_val) else None,
        "Signal": signal,
        "Position": position_qty
    }


# Function to run all stocks once
def run_trade_execution(symbols_to_process):
    results = []
    st.subheader("Trade Execution Results")
    num_cols = min(len(symbols_to_process), 3) if symbols_to_process else 1
    cols = st.columns(num_cols)
    
    for i, symbol in enumerate(symbols_to_process):
        with cols[i % max(1, num_cols)]: 
            result = process_stock(symbol, qty=1)
            if isinstance(result, dict):
                results.append(result)
                st.markdown(f"**{symbol} Trade Status**")
                st.json(result) 
            else:
                st.warning(result)
    
    if results:
        st.markdown("### Latest Trade Status Summary")
        st.dataframe(pd.DataFrame(results))
    return results


if selected_symbols:
    # 1. Display 1-Week Analysis Summary Table
    st.markdown("### 📊 1-Week Analysis Summary")
    analysis_results = []
    
    for sym in selected_symbols:
        analysis = analyze_stock_1week(sym)
        analysis_results.append(analysis)
    
    # Display summary table
    summary_df = pd.DataFrame([{
        "Symbol": a["Symbol"],
        "Price": a["Price"],
        "Week %": a["Week_Change_%"],
        "RSI": a["RSI"],
        "Tech Signal": a["Tech_Signal"],
        "News Signal": a["News_Signal"],
        "Final Signal": a["Final_Signal"],
        "Confidence": a["Confidence"]
    } for a in analysis_results])
    
    # Color code the signals
    def color_signal(val):
        if "STRONG BUY" in str(val) or "BUY" in str(val):
            return 'background-color: #90EE90'
        elif "STRONG SELL" in str(val) or "SELL" in str(val):
            return 'background-color: #FFB6C1'
        elif "HOLD" in str(val):
            return 'background-color: #FFE4B5'
        return ''
    
    styled_df = summary_df.style.applymap(color_signal, subset=['Tech Signal', 'News Signal', 'Final Signal'])
    st.dataframe(styled_df, use_container_width=True)

    st.markdown("---")

    # 2. Detailed Analysis for Each Stock
    st.markdown("### 📈 Detailed Stock Analysis with News & Charts")
    
    for analysis in analysis_results:
        sym = analysis["Symbol"]
        st.markdown("---")
        st.markdown(f"## 📊 {sym} - Detailed Analysis")
        
        # Create three columns for key metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Current Price", analysis["Price"], f"{analysis['Week_Change_%']}% (1W)")
            st.metric("RSI", analysis["RSI"])
        
        with col2:
            signal_emoji = "🟢" if "BUY" in analysis["Final_Signal"] else "🔴" if "SELL" in analysis["Final_Signal"] else "🟡"
            st.metric("Final Signal", f"{signal_emoji} {analysis['Final_Signal']}")
            st.metric("Confidence", analysis["Confidence"])
        
        with col3:
            st.metric("Tech Signal", analysis["Tech_Signal"])
            st.metric("News Signal", f"{analysis['News_Signal']} ({analysis['News_Score']})")
        
        # Analysis Reasoning
        st.markdown("#### 🔍 Analysis Reasoning")
        st.info(analysis["Reasons"])
        
        # 1-Week Chart with Technical Indicators
        st.markdown("#### 📈 1-Week Price Chart (Yahoo Finance)")
        week_data = analysis.get("week_data")
        if week_data is not None and not week_data.empty:
            fig = go.Figure()
            
            # Candlestick chart
            fig.add_trace(go.Candlestick(
                x=week_data.index,
                open=week_data['Open'],
                high=week_data['High'],
                low=week_data['Low'],
                close=week_data['Close'],
                name='Price'
            ))
            
            # Add MA5
            if 'MA5' in week_data.columns:
                fig.add_trace(go.Scatter(
                    x=week_data.index,
                    y=week_data['MA5'],
                    mode='lines',
                    name='MA5',
                    line=dict(color='orange', width=2)
                ))
            
            # Add MA10
            if 'MA10' in week_data.columns:
                fig.add_trace(go.Scatter(
                    x=week_data.index,
                    y=week_data['MA10'],
                    mode='lines',
                    name='MA10',
                    line=dict(color='blue', width=2)
                ))
            
            fig.update_layout(
                title=f'{sym} - 1 Week Price Action',
                yaxis_title='Price (USD)',
                xaxis_title='Date',
                height=500,
                template='plotly_white',
                xaxis_rangeslider_visible=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Volume chart
            fig_vol = go.Figure()
            fig_vol.add_trace(go.Bar(
                x=week_data.index,
                y=week_data['Volume'],
                name='Volume',
                marker_color='lightblue'
            ))
            
            if 'Volume_MA' in week_data.columns:
                fig_vol.add_trace(go.Scatter(
                    x=week_data.index,
                    y=week_data['Volume_MA'],
                    mode='lines',
                    name='Volume MA',
                    line=dict(color='red', width=2)
                ))
            
            fig_vol.update_layout(
                title=f'{sym} - Trading Volume',
                yaxis_title='Volume',
                height=300,
                template='plotly_white'
            )
            
            st.plotly_chart(fig_vol, use_container_width=True)
        else:
            st.warning("No chart data available")
        
        # News & Blogs Section
        st.markdown("#### 📰 Latest News & Market Sentiment")
        news_details = analysis.get("news_details", [])
        
        if news_details:
            for i, news in enumerate(news_details, 1):
                with st.expander(f"📰 {i}. {news['title'][:80]}..."):
                    st.markdown(f"**Publisher:** {news['publisher']}")
                    st.markdown(f"**Published:** {news['time']}")
                    st.markdown(f"**Link:** [{news['title']}]({news['link']})")
        else:
            st.caption("No recent news available for this symbol.")
        
        # Execute Trade Button (if Alpaca is connected)
        if api is not None and analysis["Final_Signal"] in ["STRONG BUY", "STRONG SELL"]:
            st.markdown("#### 💰 Execute Trade on Alpaca")
            
            col_trade1, col_trade2 = st.columns([2, 1])
            
            with col_trade1:
                qty_input = st.number_input(
                    f"Quantity to trade for {sym}",
                    min_value=1,
                    value=10,
                    key=f"qty_{sym}"
                )
            
            with col_trade2:
                if analysis["Final_Signal"] == "STRONG BUY":
                    if st.button(f"🟢 BUY {sym}", key=f"buy_{sym}", type="primary"):
                        try:
                            # Calculate stop loss and take profit
                            current_price = float(analysis["Price"].replace("$", ""))
                            stop_loss = current_price * 0.95  # 5% stop loss
                            take_profit = current_price * 1.10  # 10% take profit
                            
                            order = api.submit_order(
                                symbol=sym,
                                qty=qty_input,
                                side="buy",
                                type="market",
                                time_in_force="gtc",
                                order_class="bracket",
                                take_profit=dict(limit_price=round(take_profit, 2)),
                                stop_loss=dict(stop_price=round(stop_loss, 2))
                            )
                            st.success(f"✅ BUY order submitted for {qty_input} shares of {sym}!")
                            st.json({
                                "Order ID": order.id,
                                "Symbol": sym,
                                "Qty": qty_input,
                                "Stop Loss": f"${stop_loss:.2f}",
                                "Take Profit": f"${take_profit:.2f}"
                            })
                        except Exception as e:
                            st.error(f"❌ Error submitting order: {e}")
                
                elif analysis["Final_Signal"] == "STRONG SELL":
                    if st.button(f"🔴 SELL {sym}", key=f"sell_{sym}", type="secondary"):
                        try:
                            # Check if position exists
                            try:
                                position = api.get_position(sym)
                                position_qty = int(position.qty)
                                
                                order = api.submit_order(
                                    symbol=sym,
                                    qty=min(qty_input, position_qty),
                                    side="sell",
                                    type="market",
                                    time_in_force="gtc"
                                )
                                st.success(f"✅ SELL order submitted for {min(qty_input, position_qty)} shares of {sym}!")
                                st.json({"Order ID": order.id, "Symbol": sym, "Qty": min(qty_input, position_qty)})
                            except:
                                st.warning(f"No position found for {sym}. Cannot sell.")
                        except Exception as e:
                            st.error(f"❌ Error submitting order: {e}")


if selected_symbols:
    trend_rows = []
    
    # OLD 1-Month Trend Summary Table (kept for backward compatibility)
    with st.expander("📅 View Legacy 1-Month Trend Analysis"):
        st.markdown("### 1-Month Trend Summary Table")
        for sym in selected_symbols:
            trend_rows.append(analyze_trend(sym))
        st.dataframe(pd.DataFrame(trend_rows))

# ------------------------------
# Manual Trade Execution
# ------------------------------
if run_manual_trade and tickers_for_trade:
    run_trade_execution(tickers_for_trade)
elif run_manual_trade and not tickers_for_trade:
    st.warning("Please select tickers to run the manual trade check.")


# ------------------------------
# Auto-trade execution
# ------------------------------
if auto_trade:
    st.subheader("Auto-Trade Running...")
    # This runs the trade execution and orders will be submitted due to the 'auto_trade' flag
    if api is None:
        st.error("Alpaca API keys are missing. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in Streamlit secrets/environment to enable trading.")
    else:
        run_trade_execution(tickers_for_trade)
        st.write(f"Next update in **{refresh_interval} minutes**")
        # Streamlit will rerun every refresh_interval minutes
        time.sleep(refresh_interval * 60)
        st.rerun() # re-run script to fetch latest data