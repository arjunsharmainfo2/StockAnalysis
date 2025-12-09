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
    st.warning("Alpaca API credentials not set. Viewing data-only mode. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in environment/Streamlit secrets to enable live data and trading.")

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
# NEW: Yahoo Finance Analysis Function
# ------------------------------
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
        
        summary = f"PE: {pe_ratio} | 52W High: ${fifty_two_week_high} | 52W Low: ${fifty_two_week_low}"
        
        return {
            "Summary": summary,
            "Market Cap": f"${market_cap:,.0f}" if isinstance(market_cap, (int, float)) else market_cap
        }
    except Exception as e:
        return {
            "Summary": "Data unavailable",
            "Market Cap": "N/A"
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
        news_items = news_items[:limit] if news_items else []
    except Exception as e:
        print(f"{symbol} news fetch error: {e}")
        news_items = []

    scores = []
    headlines = []
    for item in news_items:
        title = item.get("title") or ""
        if not title:
            continue
        headlines.append(title)
        scores.append(_score_headline(title))

    if not scores:
        return {"symbol": symbol, "news_signal": "HOLD", "news_score": 0.0, "headlines": [], "empty": True}

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
        "empty": False,
    }

# ------------------------------
# 1M trend analysis UI
# ------------------------------
st.subheader("1M Trend Analysis")

# Use the same tickers from main input for analysis
selected_symbols = tickers_for_trade if tickers_for_trade else []
st.caption(f"Analyzing {len(selected_symbols)} tickers for trends and signals.")


# --- Helper functions for data retrieval and plotting ---

@st.cache_data(ttl=600)
def get_trend_data(symbol, _timeframe=TimeFrame.Day, limit=30, ma1=10, ma2=20):
    """Fetches bar data and calculates MAs for trend analysis. Cached for 10 minutes.
    Note: _timeframe is excluded from cache hash (prefixed with underscore)."""
    if api is None:
        return None
    try:
        df = api.get_bars(symbol, _timeframe, limit=limit).df
        if df.empty:
            return None
        
        df[f"ma{ma1}"] = df["close"].rolling(window=ma1).mean()
        df[f"ma{ma2}"] = df["close"].rolling(window=ma2).mean()
        return df
    except Exception as e:
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
    trend_rows = []
    
    # 1. Display summary table
    st.markdown("### 1-Month Trend Summary Table")
    for sym in selected_symbols:
        trend_rows.append(analyze_trend(sym))
    st.dataframe(pd.DataFrame(trend_rows))

    st.markdown("---")

    # 2. Display Yahoo News, Analysis, and Plots
    st.markdown("### Fundamental Context, News, and Technical Visualizations")
    
    for sym in selected_symbols:
        st.markdown("---")
        st.markdown(f"## 📊 {sym} Analysis")
        
        # Fetch Yahoo Data
        yahoo_data = get_yahoo_analysis(sym)
        news_data = get_news_signal(sym)
        
        # Display Summary Info in columns
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**📈 Info:** {yahoo_data['Summary']}")
            st.markdown(f"**💰 Market Cap:** {yahoo_data['Market Cap']}")
        with col2:
            st.markdown(f"**📰 News Signal:** {news_data.get('news_signal')} (score {news_data.get('news_score')})")
        
        # Display News Headlines - ALWAYS VISIBLE
        st.markdown("#### 📰 Recent News Headlines")
        headlines = news_data.get("headlines", [])
        if headlines:
            for h in headlines:
                st.write(f"• {h}")
        else:
            st.caption("No recent Yahoo Finance headlines returned for this symbol.")
        
        # Display 30-Day Technical Chart - ALWAYS VISIBLE
        st.markdown("#### 📈 30-Day Technical Chart")
        df = get_trend_data(sym, _timeframe=TimeFrame.Day, limit=30, ma1=10, ma2=20)
        plot_analysis(df, sym, "30 Day Bars")


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