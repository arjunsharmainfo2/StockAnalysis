"""
Watchlist Manager Page - Add/remove stocks and manage auto-trading
"""
import streamlit as st
from typing import Dict
import pandas as pd


def show(user_data: Dict, db):
    """Show watchlist manager page"""
    
    st.title("📋 Watchlist Manager")
    st.markdown("Manage your stocks and auto-trading preferences")
    
    # Get current watchlist
    watchlist = db.get_user_watchlist(user_data['user_id'])
    
    # Add stocks section
    st.markdown("### ➕ Add Stocks to Watchlist")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        new_symbols = st.text_input(
            "Enter stock symbols (comma-separated)",
            placeholder="e.g., AAPL, MSFT, GOOGL, AMZN, TSLA",
            help="Add multiple stocks at once, separated by commas"
        )
    
    with col2:
        enable_auto_trade = st.checkbox("Enable Auto-Trade", value=False)
    
    if st.button("Add to Watchlist", type="primary"):
        if new_symbols:
            symbol_list = [s.strip().upper() for s in new_symbols.split(',') if s.strip()]
            
            success_count = 0
            errors = []
            
            for symbol in symbol_list:
                if db.add_to_watchlist(user_data['user_id'], symbol, enable_auto_trade):
                    success_count += 1
                else:
                    errors.append(symbol)
            
            if success_count > 0:
                st.success(f"✅ Successfully added {success_count} stock(s)!")
                st.rerun()
            
            if errors:
                st.warning(f"⚠️ Some stocks might already be in your watchlist: {', '.join(errors)}")
        else:
            st.warning("Please enter at least one stock symbol")
    
    st.markdown("---")
    
    # Current watchlist
    st.markdown("### 📊 Current Watchlist")
    
    if not watchlist:
        st.info("Your watchlist is empty. Add stocks above to get started!")
        return
    
    st.caption(f"Total Stocks: {len(watchlist)}")
    
    # Display watchlist with controls
    for item in watchlist:
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 2])
        
        with col1:
            st.markdown(f"### {item['symbol']}")
        
        with col2:
            added_date = pd.to_datetime(item['added_at']).strftime('%Y-%m-%d')
            st.caption(f"Added: {added_date}")
        
        with col3:
            # Auto-trade toggle
            auto_trade_enabled = bool(item['auto_trade_enabled'])
            new_state = st.checkbox(
                "Auto-Trade",
                value=auto_trade_enabled,
                key=f"auto_{item['symbol']}"
            )
            
            if new_state != auto_trade_enabled:
                if db.toggle_auto_trade(user_data['user_id'], item['symbol'], new_state):
                    st.success(f"Updated {item['symbol']}")
                    st.rerun()
        
        with col4:
            if st.button("View Details", key=f"view_{item['symbol']}"):
                st.session_state.selected_stock = item['symbol']
                st.session_state.page = "Stock Details"
                st.rerun()
        
        with col5:
            if st.button("🗑️ Remove", key=f"remove_{item['symbol']}", type="secondary"):
                if db.remove_from_watchlist(user_data['user_id'], item['symbol']):
                    st.success(f"Removed {item['symbol']}")
                    st.rerun()
        
        st.markdown("---")
    
    # Bulk actions
    st.markdown("### ⚡ Bulk Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Enable Auto-Trade for All", use_container_width=True):
            count = 0
            for item in watchlist:
                if db.toggle_auto_trade(user_data['user_id'], item['symbol'], True):
                    count += 1
            st.success(f"Enabled auto-trade for {count} stocks")
            st.rerun()
    
    with col2:
        if st.button("Disable Auto-Trade for All", use_container_width=True):
            count = 0
            for item in watchlist:
                if db.toggle_auto_trade(user_data['user_id'], item['symbol'], False):
                    count += 1
            st.success(f"Disabled auto-trade for {count} stocks")
            st.rerun()
    
    with col3:
        if st.button("⚠️ Clear All", type="secondary", use_container_width=True):
            if st.session_state.get('confirm_clear', False):
                count = 0
                for item in watchlist:
                    if db.remove_from_watchlist(user_data['user_id'], item['symbol']):
                        count += 1
                st.success(f"Removed {count} stocks")
                st.session_state.confirm_clear = False
                st.rerun()
            else:
                st.session_state.confirm_clear = True
                st.warning("Click again to confirm clearing all stocks")
    
    # Popular stocks suggestions
    st.markdown("---")
    st.markdown("### 💡 Popular Stocks")
    
    popular_stocks = {
        "Tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
        "Finance": ["JPM", "BAC", "WFC", "GS", "MS", "C"],
        "Healthcare": ["JNJ", "UNH", "PFE", "ABBV", "TMO"],
        "Consumer": ["WMT", "HD", "MCD", "NKE", "SBUX"],
        "Energy": ["XOM", "CVX", "COP", "SLB"]
    }
    
    category = st.selectbox("Select Category", list(popular_stocks.keys()))
    
    st.markdown(f"**{category} Stocks:**")
    
    cols = st.columns(7)
    for idx, symbol in enumerate(popular_stocks[category]):
        with cols[idx % 7]:
            if st.button(symbol, key=f"popular_{symbol}", use_container_width=True):
                if db.add_to_watchlist(user_data['user_id'], symbol, False):
                    st.success(f"Added {symbol}!")
                    st.rerun()
