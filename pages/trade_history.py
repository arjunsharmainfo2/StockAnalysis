"""
Trade History Page - View all past trades and performance
"""
import streamlit as st
from typing import Dict
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


def calculate_pnl(trades_df: pd.DataFrame) -> Dict:
    """Calculate P&L from trades"""
    if trades_df.empty:
        return {
            'total_pnl': 0,
            'realized_pnl': 0,
            'win_rate': 0,
            'total_trades': 0,
            'profitable_trades': 0
        }
    
    # Simple P&L calculation
    buy_trades = trades_df[trades_df['side'] == 'BUY']
    sell_trades = trades_df[trades_df['side'] == 'SELL']
    
    total_bought = (buy_trades['quantity'] * buy_trades['price']).sum()
    total_sold = (sell_trades['quantity'] * sell_trades['price']).sum()
    
    realized_pnl = total_sold - total_bought
    
    # Win rate calculation (simplified)
    profitable = len(sell_trades[sell_trades['price'] > buy_trades['price'].mean()])
    win_rate = (profitable / len(sell_trades) * 100) if len(sell_trades) > 0 else 0
    
    return {
        'total_pnl': realized_pnl,
        'realized_pnl': realized_pnl,
        'win_rate': win_rate,
        'total_trades': len(trades_df),
        'profitable_trades': profitable
    }


def show(user_data: Dict, db):
    """Show trade history page"""
    
    st.title("📊 Trade History & Performance")
    
    # Get all trades
    trades_df = db.get_user_trades(user_data['user_id'], limit=1000)
    
    if trades_df.empty:
        st.info("📭 No trades yet. Start trading from the Dashboard or Stock Details page!")
        return
    
    # Calculate metrics
    metrics = calculate_pnl(trades_df)
    
    # Display key metrics
    st.markdown("### 📈 Performance Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        pnl_color = "normal" if metrics['total_pnl'] >= 0 else "inverse"
        st.metric(
            "Total P&L",
            f"${metrics['total_pnl']:.2f}",
            delta=f"{metrics['total_pnl']:.2f}",
            delta_color=pnl_color
        )
    
    with col2:
        st.metric("Total Trades", metrics['total_trades'])
    
    with col3:
        st.metric("Win Rate", f"{metrics['win_rate']:.1f}%")
    
    with col4:
        st.metric("Profitable Trades", metrics['profitable_trades'])
    
    st.markdown("---")
    
    # Filters
    st.markdown("### 🔍 Filter Trades")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Filter by symbol
        all_symbols = ['All'] + sorted(trades_df['symbol'].unique().tolist())
        selected_symbol = st.selectbox("Symbol", all_symbols)
    
    with col2:
        # Filter by action
        actions = ['All'] + sorted(trades_df['action'].unique().tolist())
        selected_action = st.selectbox("Action", actions)
    
    with col3:
        # Filter by side
        sides = ['All'] + sorted(trades_df['side'].unique().tolist())
        selected_side = st.selectbox("Side", sides)
    
    # Apply filters
    filtered_df = trades_df.copy()
    
    if selected_symbol != 'All':
        filtered_df = filtered_df[filtered_df['symbol'] == selected_symbol]
    
    if selected_action != 'All':
        filtered_df = filtered_df[filtered_df['action'] == selected_action]
    
    if selected_side != 'All':
        filtered_df = filtered_df[filtered_df['side'] == selected_side]
    
    st.caption(f"Showing {len(filtered_df)} of {len(trades_df)} trades")
    
    # Display trades table
    st.markdown("### 📋 Trade Log")
    
    # Format the dataframe for display
    display_df = filtered_df.copy()
    display_df['executed_at'] = pd.to_datetime(display_df['executed_at']).dt.strftime('%Y-%m-%d %H:%M')
    display_df['total_value'] = display_df['quantity'] * display_df['price']
    display_df['total_value'] = display_df['total_value'].apply(lambda x: f"${x:.2f}")
    display_df['price'] = display_df['price'].apply(lambda x: f"${x:.2f}")
    
    st.dataframe(
        display_df[['executed_at', 'symbol', 'action', 'side', 'quantity', 'price', 'total_value', 'status']],
        use_container_width=True,
        hide_index=True
    )
    
    # Download button
    csv = filtered_df.to_csv(index=False)
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name=f"trades_{user_data['username']}_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )
    
    st.markdown("---")
    
    # Visualizations
    st.markdown("### 📊 Analytics")
    
    tab1, tab2, tab3 = st.tabs(["Trade Volume", "P&L by Symbol", "Trade Timeline"])
    
    with tab1:
        # Trade volume by symbol
        symbol_counts = trades_df['symbol'].value_counts()
        
        fig = px.bar(
            x=symbol_counts.index,
            y=symbol_counts.values,
            labels={'x': 'Symbol', 'y': 'Number of Trades'},
            title='Trade Volume by Symbol'
        )
        fig.update_layout(height=400, template='plotly_white')
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        # P&L by symbol (simplified)
        symbol_pnl = trades_df.groupby('symbol').apply(
            lambda x: (x[x['side'] == 'SELL']['quantity'] * x[x['side'] == 'SELL']['price']).sum() -
                     (x[x['side'] == 'BUY']['quantity'] * x[x['side'] == 'BUY']['price']).sum()
        ).sort_values(ascending=False)
        
        colors = ['green' if x > 0 else 'red' for x in symbol_pnl.values]
        
        fig = go.Figure(data=[
            go.Bar(
                x=symbol_pnl.index,
                y=symbol_pnl.values,
                marker_color=colors
            )
        ])
        
        fig.update_layout(
            title='P&L by Symbol',
            xaxis_title='Symbol',
            yaxis_title='P&L ($)',
            height=400,
            template='plotly_white'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        # Trade timeline
        trades_df['executed_at'] = pd.to_datetime(trades_df['executed_at'])
        trades_df = trades_df.sort_values('executed_at')
        
        trades_df['cumulative_value'] = (
            trades_df.apply(
                lambda x: x['quantity'] * x['price'] * (1 if x['side'] == 'SELL' else -1),
                axis=1
            ).cumsum()
        )
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=trades_df['executed_at'],
            y=trades_df['cumulative_value'],
            mode='lines+markers',
            name='Cumulative P&L',
            line=dict(color='blue', width=2),
            marker=dict(size=8)
        ))
        
        fig.update_layout(
            title='Cumulative P&L Over Time',
            xaxis_title='Date',
            yaxis_title='Cumulative P&L ($)',
            height=400,
            template='plotly_white',
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Recent trades summary
    st.markdown("---")
    st.markdown("### 🕐 Recent Trades")
    
    recent_trades = trades_df.head(10)
    
    for _, trade in recent_trades.iterrows():
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 2])
        
        with col1:
            st.markdown(f"**{trade['symbol']}**")
        
        with col2:
            action_color = "🟢" if trade['side'] == "BUY" else "🔴"
            st.markdown(f"{action_color} {trade['side']}")
        
        with col3:
            st.markdown(f"{trade['quantity']} shares")
        
        with col4:
            st.markdown(f"${trade['price']:.2f}")
        
        with col5:
            exec_time = pd.to_datetime(trade['executed_at']).strftime('%m/%d %H:%M')
            st.caption(exec_time)
