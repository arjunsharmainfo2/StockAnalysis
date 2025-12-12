"""
Stock Details Page - Detailed analysis of individual stocks
"""
import streamlit as st
import pandas as pd
import yfinance as yf
from typing import Dict
import plotly.graph_objects as go
from datetime import datetime
from alpaca_trade_api.rest import REST
import sys
import os

# Import the advanced stock analyzer
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stock_analyzer import StockAnalyzer


def analyze_stock_detailed(symbol: str) -> Dict:
    """Comprehensive stock analysis using CAN SLIM methodology"""
    try:
        # Use advanced analyzer
        analyzer = StockAnalyzer(symbol)
        full_analysis = analyzer.generate_signal()
        
        if full_analysis['signal'] == 'ERROR':
            return None
        
        # Get historical data for charts
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1mo", interval="1d")
        
        if hist.empty:
            return None
        
        # Calculate basic technical indicators for charts
        hist['MA5'] = hist['Close'].rolling(window=5).mean()
        hist['MA10'] = hist['Close'].rolling(window=10).mean()
        hist['MA20'] = hist['Close'].rolling(window=20).mean()
        hist['MA50'] = hist['Close'].rolling(window=50).mean()
        
        # Get news
        news_items = []
        try:
            news = ticker.news[:10]
            for item in news:
                news_items.append({
                    'title': item.get('title', ''),
                    'publisher': item.get('publisher', 'Unknown'),
                    'link': item.get('link', ''),
                    'published': datetime.fromtimestamp(item.get('providerPublishTime', 0)).strftime('%Y-%m-%d %H:%M')
                })
        except:
            pass
        
        # Get company info
        info = ticker.info
        
        # Extract comprehensive analysis
        analysis = full_analysis.get('analysis', {})
        
        return {
            'symbol': symbol,
            'hist': hist,
            'current_price': hist['Close'].iloc[-1],
            'week_change': ((hist['Close'].iloc[-1] - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5] * 100) if len(hist) >= 5 else 0,
            'news': news_items,
            'info': info,
            # Comprehensive analysis data
            'full_analysis': full_analysis,
            'signal': full_analysis['signal'],
            'confidence': full_analysis['confidence'],
            'reason': full_analysis['reason'],
            'buy_score': full_analysis['buy_score'],
            'buy_criteria_met': full_analysis['buy_criteria_met'],
            'eps_growth': analysis.get('eps_growth', {}),
            'annual_growth': analysis.get('annual_growth', {}),
            'pe_ratio': analysis.get('pe_ratio', {}),
            'peg_ratio': analysis.get('peg_ratio', {}),
            'moving_averages': analysis.get('moving_averages', {}),
            'relative_strength': analysis.get('relative_strength', {}),
            'volume': analysis.get('volume', {}),
            'market_trend': analysis.get('market_trend', {})
        }
    except Exception as e:
        st.error(f"Error analyzing {symbol}: {e}")
        return None
        st.error(f"Error analyzing {symbol}: {e}")
        return None


def show(user_data: Dict, db):
    """Show stock details page"""
    
    st.title("📈 Stock Details & Analysis")
    
    # Stock selector
    watchlist = db.get_user_watchlist(user_data['user_id'])
    symbols = [w['symbol'] for w in watchlist]
    
    if not symbols:
        st.warning("No stocks in your watchlist. Add stocks from the Watchlist Manager.")
        return
    
    # Check if coming from dashboard with selected stock
    default_index = 0
    if 'selected_stock' in st.session_state and st.session_state.selected_stock in symbols:
        default_index = symbols.index(st.session_state.selected_stock)
    
    selected_symbol = st.selectbox(
        "Select Stock to Analyze",
        options=symbols,
        index=default_index
    )
    
    if not selected_symbol:
        return
    
    # Analyze stock
    with st.spinner(f"Analyzing {selected_symbol}..."):
        analysis = analyze_stock_detailed(selected_symbol)
    
    if not analysis:
        st.error("Failed to analyze stock")
        return
    
    # Display header with signal
    signal = analysis['signal']
    confidence = analysis['confidence']
    
    if signal in ['STRONG BUY', 'BUY']:
        signal_color = 'green'
        signal_emoji = '🟢'
    elif signal == 'SELL':
        signal_color = 'red'
        signal_emoji = '🔴'
    else:
        signal_color = 'orange'
        signal_emoji = '🟡'
    
    st.markdown(f"## {selected_symbol} - {analysis['info'].get('longName', selected_symbol)}")
    
    # Signal banner
    st.markdown(f"""
    <div style='background-color: {signal_color}; padding: 20px; border-radius: 10px; text-align: center;'>
        <h1 style='color: white; margin: 0;'>{signal_emoji} {signal}</h1>
        <h3 style='color: white; margin: 5px 0;'>Confidence: {confidence}%</h3>
        <p style='color: white; font-size: 16px; margin: 5px 0;'>{analysis['reason']}</p>
        <p style='color: white; font-size: 14px; margin: 5px 0;'>Buy Score: {analysis['buy_score']}</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Key metrics row
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Current Price", f"${analysis['current_price']:.2f}")
    
    with col2:
        week_change = analysis['week_change']
        st.metric("Week Change", f"{week_change:.2f}%", 
                 delta=f"{week_change:.2f}%")
    
    with col3:
        ma_data = analysis['moving_averages']
        if ma_data.get('golden_cross'):
            st.metric("Golden Cross", "✅ YES", delta="Strong Buy Signal")
        else:
            above_50 = "✅" if ma_data.get('above_50') else "❌"
            st.metric("Above 50-day MA", above_50)
    
    with col4:
        eps_data = analysis['eps_growth']
        if eps_data.get('yoy_growth'):
            eps_icon = "✅" if eps_data['meets_criteria'] else "⚠️"
            st.metric("EPS Growth", f"{eps_data['yoy_growth']:.1f}% {eps_icon}")
        else:
            st.metric("EPS Growth", "N/A")
    
    with col5:
        pe_data = analysis['pe_ratio']
        if pe_data.get('pe_ratio'):
            pe_icon = "✅" if pe_data.get('undervalued') else "📊"
            st.metric("P/E Ratio", f"{pe_data['pe_ratio']:.1f} {pe_icon}")
        else:
            st.metric("P/E Ratio", "N/A")
    
    st.markdown("---")
    
    # Tabs for different views
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🎯 CAN SLIM Analysis", "📊 Charts", "📰 News", "ℹ️ Info", "💰 Trade"])
    
    with tab1:
        st.markdown("### 🎯 Comprehensive CAN SLIM Analysis")
        st.caption("All criteria evaluated for buy/sell/hold decision")
        
        # BUY CRITERIA CHECKLIST
        st.markdown("#### ✅ Buy Criteria Checklist (Must Meet All for Strong Buy)")
        buy_criteria = analysis['buy_criteria_met']
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.markdown("**1️⃣ Fundamental Criteria**")
            fund_check = buy_criteria.get('fundamental', False)
            st.markdown(f"{'✅' if fund_check else '❌'} EPS & Sales Growth > 20-25%")
            
            # EPS Growth Detail
            eps_data = analysis['eps_growth']
            if eps_data.get('yoy_growth') is not None:
                st.info(f"📊 **EPS Growth:** {eps_data['yoy_growth']:.2f}% YoY\n\n"
                       f"Target: >25% | {'✅ PASS' if eps_data['meets_criteria'] else '❌ FAIL'}")
            else:
                st.warning("EPS data not available")
            
            # Annual Growth Detail
            annual_data = analysis['annual_growth']
            if annual_data.get('avg_growth') is not None:
                st.info(f"📈 **3-Year Avg Growth:** {annual_data['avg_growth']:.2f}%\n\n"
                       f"Target: >25% | {'✅ PASS' if annual_data['meets_criteria'] else '❌ FAIL'}")
            
            st.markdown("---")
            
            st.markdown("**2️⃣ Technical Criteria**")
            tech_check = buy_criteria.get('technical', False)
            st.markdown(f"{'✅' if tech_check else '❌'} Price above 50-day & 200-day MA")
            
            # Moving Averages Detail
            ma_data = analysis['moving_averages']
            if ma_data.get('current_price'):
                st.info(f"📊 **Current Price:** ${ma_data['current_price']:.2f}\n\n"
                       f"**50-day MA:** ${ma_data.get('ma_50', 0):.2f} | {'✅ Above' if ma_data.get('above_50') else '❌ Below'}\n\n"
                       f"**200-day MA:** ${ma_data.get('ma_200', 0):.2f} | {'✅ Above' if ma_data.get('above_200') else '❌ Below'}")
                
                if ma_data.get('golden_cross'):
                    st.success("⭐ **GOLDEN CROSS DETECTED!** - Strong buy signal (50-day crossed above 200-day)")
        
        with col_b:
            st.markdown("**3️⃣ Volume Breakout**")
            vol_check = buy_criteria.get('volume', False)
            st.markdown(f"{'✅' if vol_check else '❌'} Volume >40-50% above average")
            
            # Volume Detail
            vol_data = analysis['volume']
            if vol_data.get('current_volume'):
                vol_increase = vol_data.get('volume_increase_pct', 0)
                st.info(f"📊 **Current Volume:** {vol_data['current_volume']:,.0f}\n\n"
                       f"**Avg Volume:** {vol_data['avg_volume']:,.0f}\n\n"
                       f"**Increase:** {vol_increase:+.1f}% | {'✅ BREAKOUT' if vol_data.get('breakout') else '❌ Normal'}")
            
            st.markdown("---")
            
            st.markdown("**4️⃣ Market Trend**")
            market_check = buy_criteria.get('market', False)
            st.markdown(f"{'✅' if market_check else '❌'} S&P 500 in uptrend")
            
            # Market Trend Detail
            market_data = analysis['market_trend']
            if market_data.get('spy_price'):
                st.info(f"📊 **S&P 500 (SPY):** ${market_data['spy_price']:.2f}\n\n"
                       f"**50-day MA:** ${market_data.get('spy_ma_50', 0):.2f}\n\n"
                       f"**Trend:** {'✅ UPTREND' if market_data.get('uptrend') else '❌ DOWNTREND'}")
        
        st.markdown("---")
        
        # VALUATION METRICS
        st.markdown("#### 💰 Valuation Metrics")
        
        val_col1, val_col2, val_col3 = st.columns(3)
        
        with val_col1:
            pe_data = analysis['pe_ratio']
            if pe_data.get('pe_ratio'):
                st.metric("P/E Ratio", f"{pe_data['pe_ratio']:.2f}")
                st.caption(f"Industry Avg: {pe_data.get('industry_pe', 'N/A')}")
                st.caption(f"Sector: {pe_data.get('sector', 'Unknown')}")
                if pe_data.get('undervalued'):
                    st.success(f"✅ Undervalued by {pe_data.get('discount_pct', 0):.1f}%")
                else:
                    st.warning("⚠️ Not undervalued vs industry")
            else:
                st.metric("P/E Ratio", "N/A")
        
        with val_col2:
            peg_data = analysis['peg_ratio']
            if peg_data.get('peg_ratio'):
                st.metric("PEG Ratio", f"{peg_data['peg_ratio']:.2f}")
                st.caption("Target: <1.0 for undervalued growth")
                if peg_data.get('undervalued'):
                    st.success("✅ Undervalued growth stock")
                else:
                    st.warning("⚠️ Not undervalued for growth")
            else:
                st.metric("PEG Ratio", "N/A")
        
        with val_col3:
            rs_data = analysis['relative_strength']
            if rs_data.get('rs_rating'):
                st.metric("RS Rating", f"{rs_data['rs_rating']:.0f}/100")
                st.caption(f"Outperformance: {rs_data.get('outperformance', 0):+.1f}%")
                if rs_data.get('meets_criteria'):
                    st.success("✅ Outperforming 80%+ of market")
                else:
                    st.warning("⚠️ Below 80 rating")
            else:
                st.metric("RS Rating", "N/A")
        
        st.markdown("---")
        
        # DECISION SUMMARY
        st.markdown("#### 📋 Decision Summary")
        
        score_parts = analysis['buy_score'].split('/')
        score_num = int(score_parts[0])
        score_total = int(score_parts[1])
        
        # Progress bar for buy score
        st.progress(score_num / score_total)
        st.markdown(f"**Buy Criteria Met:** {score_num} out of {score_total}")
        
        # Decision explanation
        if signal in ['STRONG BUY', 'BUY']:
            st.success(f"### ✅ RECOMMENDATION: {signal}")
            st.markdown(f"**Confidence Level:** {confidence}%")
            st.markdown(f"**Reasoning:** {analysis['reason']}")
            st.info("💡 **Action:** Consider entering a position with proper stop-loss (7-8% below entry)")
        elif signal == 'SELL':
            st.error(f"### ❌ RECOMMENDATION: {signal}")
            st.markdown(f"**Confidence Level:** {confidence}%")
            st.markdown(f"**Reasoning:** {analysis['reason']}")
            st.warning("⚠️ **Action:** Exit position or avoid entry")
        else:
            st.warning(f"### 🟡 RECOMMENDATION: {signal}")
            st.markdown(f"**Confidence Level:** {confidence}%")
            st.markdown(f"**Reasoning:** {analysis['reason']}")
            st.info("💡 **Action:** Monitor for entry signals or maintain current position")
    
    with tab2:
        # Candlestick chart
        st.markdown("### Price Chart with Technical Indicators")
        
        fig = go.Figure()
        
        hist = analysis['hist']
        
        # Candlestick
        fig.add_trace(go.Candlestick(
            x=hist.index,
            open=hist['Open'],
            high=hist['High'],
            low=hist['Low'],
            close=hist['Close'],
            name='Price'
        ))
        
        # Moving averages
        fig.add_trace(go.Scatter(x=hist.index, y=hist['MA5'], name='MA5', 
                                 line=dict(color='orange', width=1)))
        fig.add_trace(go.Scatter(x=hist.index, y=hist['MA10'], name='MA10', 
                                 line=dict(color='blue', width=1)))
        fig.add_trace(go.Scatter(x=hist.index, y=hist['MA20'], name='MA20', 
                                 line=dict(color='red', width=1)))
        
        fig.update_layout(
            title=f'{selected_symbol} Price Chart',
            yaxis_title='Price (USD)',
            height=600,
            template='plotly_white',
            xaxis_rangeslider_visible=False
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Volume chart
        hist['Volume_MA'] = hist['Volume'].rolling(window=20).mean()
        
        fig_vol = go.Figure()
        fig_vol.add_trace(go.Bar(x=hist.index, y=hist['Volume'], name='Volume'))
        fig_vol.add_trace(go.Scatter(x=hist.index, y=hist['Volume_MA'], 
                                     name='Volume MA (20)', line=dict(color='red', width=2)))
        
        fig_vol.update_layout(
            title='Trading Volume',
            yaxis_title='Volume',
            height=300,
            template='plotly_white'
        )
        
        st.plotly_chart(fig_vol, use_container_width=True)
    
    with tab3:
        st.markdown("### 📰 Latest News")
        
        news = analysis['news']
        
        if news:
            for i, item in enumerate(news, 1):
                with st.expander(f"📰 {i}. {item['title'][:80]}..."):
                    st.markdown(f"**Publisher:** {item['publisher']}")
                    st.markdown(f"**Published:** {item['published']}")
                    st.markdown(f"[Read full article]({item['link']})")
        else:
            st.info("No recent news available")
    
    with tab4:
        st.markdown("### ℹ️ Company Information")
        
        info = analysis['info']
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Company Details**")
            st.markdown(f"**Sector:** {info.get('sector', 'N/A')}")
            st.markdown(f"**Industry:** {info.get('industry', 'N/A')}")
            st.markdown(f"**Market Cap:** ${info.get('marketCap', 0):,.0f}")
            st.markdown(f"**PE Ratio:** {info.get('trailingPE', 'N/A')}")
        
        with col2:
            st.markdown("**Price Metrics**")
            st.markdown(f"**52 Week High:** ${info.get('fiftyTwoWeekHigh', 'N/A')}")
            st.markdown(f"**52 Week Low:** ${info.get('fiftyTwoWeekLow', 'N/A')}")
            st.markdown(f"**Dividend Yield:** {info.get('dividendYield', 0)*100:.2f}%")
            st.markdown(f"**Beta:** {info.get('beta', 'N/A')}")
        
        st.markdown("**Description**")
        st.markdown(info.get('longBusinessSummary', 'No description available'))
    
    with tab5:
        st.markdown("### 💰 Execute Trade")
        
        # Check if API keys are set
        api_key, api_secret = db.get_user_api_keys(user_data['user_id'])
        
        if not api_key or not api_secret:
            st.warning("⚠️ Alpaca API keys not configured. Go to Settings to add your keys.")
            return
        
        # Trading interface
        col1, col2 = st.columns(2)
        
        with col1:
            trade_action = st.radio("Action", ["BUY", "SELL"], horizontal=True)
        
        with col2:
            quantity = st.number_input("Quantity", min_value=1, value=10, step=1)
        
        # Show estimated cost
        est_cost = analysis['current_price'] * quantity
        st.info(f"💵 Estimated {'Cost' if trade_action == 'BUY' else 'Value'}: ${est_cost:.2f}")
        
        # Execute button
        if st.button(f"Execute {trade_action} Order", type="primary", use_container_width=True):
            try:
                # Initialize Alpaca API
                api = REST(api_key, api_secret, "https://paper-api.alpaca.markets")
                
                # Check position for SELL
                if trade_action == "SELL":
                    try:
                        position = api.get_position(selected_symbol)
                        position_qty = int(position.qty)
                        
                        if position_qty < quantity:
                            st.error(f"Insufficient position. You have {position_qty} shares.")
                            return
                    except:
                        st.error("No position found for this symbol.")
                        return
                
                # Submit order
                if trade_action == "BUY":
                    stop_loss = analysis['current_price'] * 0.95
                    take_profit = analysis['current_price'] * 1.10
                    
                    order = api.submit_order(
                        symbol=selected_symbol,
                        qty=quantity,
                        side="buy",
                        type="market",
                        time_in_force="gtc",
                        order_class="bracket",
                        take_profit=dict(limit_price=round(take_profit, 2)),
                        stop_loss=dict(stop_price=round(stop_loss, 2))
                    )
                else:
                    order = api.submit_order(
                        symbol=selected_symbol,
                        qty=quantity,
                        side="sell",
                        type="market",
                        time_in_force="gtc"
                    )
                
                # Log trade
                db.log_trade(
                    user_id=user_data['user_id'],
                    symbol=selected_symbol,
                    action="OPEN" if trade_action == "BUY" else "CLOSE",
                    side=trade_action,
                    quantity=quantity,
                    price=analysis['current_price'],
                    order_id=order.id,
                    notes=f"Executed from Stock Details page"
                )
                
                st.success(f"✅ {trade_action} order submitted successfully!")
                st.json({
                    "Order ID": order.id,
                    "Symbol": selected_symbol,
                    "Action": trade_action,
                    "Quantity": quantity,
                    "Price": f"${analysis['current_price']:.2f}"
                })
                
            except Exception as e:
                st.error(f"❌ Error executing trade: {e}")
    
    # Trade history for this stock
    st.markdown("---")
    st.markdown("### 📊 Trade History for this Stock")
    
    trades = db.get_trades_by_symbol(user_data['user_id'], selected_symbol)
    
    if not trades.empty:
        st.dataframe(trades, use_container_width=True)
    else:
        st.info("No trades yet for this stock")
