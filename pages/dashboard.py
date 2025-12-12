"""
Dashboard Page - Summary view of all stocks in watchlist
"""
import streamlit as st
import pandas as pd
from typing import Dict
import yfinance as yf
from datetime import datetime
import plotly.graph_objects as go
import sys
import os

# Import the advanced stock analyzer
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stock_analyzer import StockAnalyzer


def get_stock_summary(symbol: str) -> Dict:
    """Get comprehensive summary of a stock using advanced analyzer"""
    try:
        # Use advanced analyzer
        analyzer = StockAnalyzer(symbol)
        result = analyzer.generate_signal()
        
        if result['signal'] == 'ERROR':
            return None
        
        # Get basic price info
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1wk")
        
        if hist.empty:
            return None
        
        current_price = hist['Close'].iloc[-1]
        week_start = hist['Close'].iloc[0]
        week_change = ((current_price - week_start) / week_start) * 100
        
        # Extract analysis details
        analysis = result.get('analysis', {})
        ma_data = analysis.get('moving_averages', {})
        eps_data = analysis.get('eps_growth', {})
        pe_data = analysis.get('pe_ratio', {})
        
        return {
            "symbol": symbol,
            "price": round(current_price, 2),
            "week_change": round(week_change, 2),
            "volume": hist['Volume'].iloc[-1],
            "signal": result['signal'],
            "confidence": result['confidence'],
            "reason": result['reason'],
            "buy_score": result['buy_score'],
            "ma_50": ma_data.get('ma_50'),
            "ma_200": ma_data.get('ma_200'),
            "above_50": ma_data.get('above_50', False),
            "above_200": ma_data.get('above_200', False),
            "golden_cross": ma_data.get('golden_cross', False),
            "eps_growth": eps_data.get('yoy_growth'),
            "pe_ratio": pe_data.get('pe_ratio'),
            "undervalued": pe_data.get('undervalued', False)
        }
    except Exception as e:
        return None


def show(user_data: Dict, db):
    """Show dashboard page"""
    
    st.title("📊 Trading Dashboard")
    st.markdown(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get user's watchlist
    watchlist = db.get_user_watchlist(user_data['user_id'])
    
    if not watchlist:
        st.info("👋 Your watchlist is empty. Go to **Watchlist Manager** to add stocks!")
        
        # Quick add form
        st.markdown("### Quick Add Stocks")
        with st.form("quick_add"):
            symbols = st.text_input(
                "Enter stock symbols (comma-separated)", 
                placeholder="e.g., AAPL, MSFT, GOOGL"
            )
            submit = st.form_submit_button("Add to Watchlist")
            
            if submit and symbols:
                symbol_list = [s.strip().upper() for s in symbols.split(',')]
                success_count = 0
                
                for symbol in symbol_list:
                    if db.add_to_watchlist(user_data['user_id'], symbol):
                        success_count += 1
                
                st.success(f"Added {success_count} stocks to watchlist!")
                st.rerun()
        
        return
    
    # Display statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Stocks", len(watchlist))
    
    with col2:
        auto_trade_count = sum(1 for w in watchlist if w['auto_trade_enabled'])
        st.metric("Auto-Trade Active", auto_trade_count)
    
    with col3:
        # Get recent trades
        trades_df = db.get_user_trades(user_data['user_id'], limit=100)
        st.metric("Total Trades", len(trades_df))
    
    with col4:
        if not trades_df.empty:
            total_pnl = 0  # Calculate P&L if needed
            st.metric("Today's P&L", "$0.00")  # Placeholder
        else:
            st.metric("Today's P&L", "$0.00")
    
    st.markdown("---")
    
    # Fetch data for all stocks
    st.markdown("### 📈 Watchlist Overview")
    
    with st.spinner("Fetching stock data..."):
        summaries = []
        
        for item in watchlist:
            summary = get_stock_summary(item['symbol'])
            if summary:
                summary['auto_trade'] = '✅' if item['auto_trade_enabled'] else '❌'
                summary['added_at'] = item['added_at']
                summaries.append(summary)
    
    if summaries:
        # Create summary dataframe
        df_summary = pd.DataFrame(summaries)
        
        # Display as interactive table with comprehensive metrics
        st.markdown("#### 📊 Comprehensive Stock Analysis")
        st.caption("Based on CAN SLIM methodology: EPS Growth, P/E Ratio, Moving Averages, Relative Strength, Volume & Market Trend")
        
        for idx, row in df_summary.iterrows():
            # Determine signal styling
            if row['signal'] in ['STRONG BUY', 'BUY']:
                signal_color = 'green'
                signal_emoji = '🟢'
            elif row['signal'] == 'SELL':
                signal_color = 'red'
                signal_emoji = '🔴'
            else:
                signal_color = 'orange'
                signal_emoji = '🟡'
            
            # Create expandable row for each stock
            with st.expander(f"{signal_emoji} **{row['symbol']}** - ${row['price']} ({row['week_change']:+.2f}%) - **{row['signal']}** ({row['confidence']}% confidence)", expanded=False):
                col1, col2, col3 = st.columns([2, 2, 2])
                
                with col1:
                    st.markdown("**📈 Technical**")
                    st.markdown(f"✓ Above 50-day MA: {'✅' if row.get('above_50') else '❌'}")
                    st.markdown(f"✓ Above 200-day MA: {'✅' if row.get('above_200') else '❌'}")
                    if row.get('golden_cross'):
                        st.markdown("⭐ **Golden Cross Detected!**")
                    if row.get('ma_50'):
                        st.caption(f"50-day MA: ${row['ma_50']:.2f}")
                    if row.get('ma_200'):
                        st.caption(f"200-day MA: ${row['ma_200']:.2f}")
                
                with col2:
                    st.markdown("**💰 Fundamentals**")
                    if row.get('eps_growth'):
                        eps_icon = '✅' if row['eps_growth'] >= 25 else '⚠️'
                        st.markdown(f"{eps_icon} EPS Growth: {row['eps_growth']:.1f}%")
                    if row.get('pe_ratio'):
                        pe_icon = '✅' if row.get('undervalued') else '📊'
                        st.markdown(f"{pe_icon} P/E Ratio: {row['pe_ratio']:.1f}")
                        if row.get('undervalued'):
                            st.caption("📉 Undervalued vs industry")
                
                with col3:
                    st.markdown("**🎯 Analysis**")
                    st.markdown(f"Buy Score: **{row.get('buy_score', 'N/A')}**")
                    st.markdown(f"Confidence: **{row['confidence']}%**")
                    st.caption(f"_{row['reason']}_")
                
                # Action buttons
                col_a, col_b, col_c = st.columns([2, 2, 2])
                with col_a:
                    if st.button("View Details", key=f"view_{row['symbol']}", use_container_width=True):
                        st.session_state.selected_stock = row['symbol']
                        st.session_state.page = "Stock Details"
                        st.rerun()
                with col_b:
                    st.markdown(f"Auto-Trade: {row['auto_trade']}")
                with col_c:
                    if st.button("Remove", key=f"remove_{row['symbol']}", type="secondary", use_container_width=True):
                        db.remove_from_watchlist(user_data['user_id'], row['symbol'])
                        st.success(f"Removed {row['symbol']}")
                        st.rerun()
        
        # Charts section
        st.markdown("### 📊 Quick Charts")
        
        # Allow user to select stocks for comparison
        selected_for_chart = st.multiselect(
            "Select stocks to compare (max 5)",
            options=[s['symbol'] for s in summaries],
            default=[summaries[0]['symbol']] if summaries else [],
            max_selections=5
        )
        
        if selected_for_chart:
            # Fetch historical data
            fig = go.Figure()
            
            for symbol in selected_for_chart:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1mo")
                
                if not hist.empty:
                    fig.add_trace(go.Scatter(
                        x=hist.index,
                        y=hist['Close'],
                        mode='lines',
                        name=symbol,
                        line=dict(width=2)
                    ))
            
            fig.update_layout(
                title="1-Month Price Comparison",
                xaxis_title="Date",
                yaxis_title="Price (USD)",
                height=500,
                template='plotly_white',
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    else:
        st.warning("No stock data available")
    
    # Auto-refresh option
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    
    with col1:
        auto_refresh = st.checkbox("Auto-refresh every 5 minutes")
    
    with col2:
        if st.button("🔄 Refresh Now", use_container_width=True):
            st.rerun()
    
    if auto_refresh:
        import time
        time.sleep(300)  # 5 minutes
        st.rerun()
