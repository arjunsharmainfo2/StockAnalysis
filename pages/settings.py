"""
Settings Page - User account and API configuration
"""
import streamlit as st
from typing import Dict


def show(user_data: Dict, db):
    """Show settings page"""
    
    st.title("⚙️ Settings")
    st.markdown("Manage your account and trading preferences")
    
    # Tabs for different settings
    tab1, tab2, tab3 = st.tabs(["🔑 API Keys", "👤 Account", "🎨 Preferences"])
    
    with tab1:
        st.markdown("### 🔑 Alpaca API Configuration")
        st.markdown("""
        Configure your Alpaca API keys to enable automated trading.
        
        - Get your API keys from [Alpaca Markets](https://alpaca.markets/)
        - Use **Paper Trading** keys for testing
        - Use **Live Trading** keys for real money trading
        """)
        
        # Get current keys
        current_api_key, current_api_secret = db.get_user_api_keys(user_data['user_id'])
        
        with st.form("api_keys_form"):
            api_key = st.text_input(
                "API Key ID",
                value=current_api_key,
                type="password",
                help="Your Alpaca API Key ID"
            )
            
            api_secret = st.text_input(
                "API Secret Key",
                value=current_api_secret,
                type="password",
                help="Your Alpaca API Secret Key"
            )
            
            base_url = st.selectbox(
                "Environment",
                ["https://paper-api.alpaca.markets", "https://api.alpaca.markets"],
                help="Use paper-api for testing, api for live trading"
            )
            
            submit = st.form_submit_button("💾 Save API Keys", use_container_width=True)
            
            if submit:
                if api_key and api_secret:
                    if db.update_user_api_keys(user_data['user_id'], api_key, api_secret):
                        db.save_setting(user_data['user_id'], 'alpaca_base_url', base_url)
                        st.success("✅ API keys updated successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to update API keys")
                else:
                    st.warning("Please enter both API key and secret")
        
        # Test connection
        if current_api_key and current_api_secret:
            st.markdown("---")
            st.markdown("### 🧪 Test Connection")
            
            if st.button("Test API Connection", use_container_width=True):
                try:
                    from alpaca_trade_api.rest import REST
                    
                    api = REST(current_api_key, current_api_secret, base_url)
                    account = api.get_account()
                    
                    st.success("✅ Connection successful!")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Account Status", account.status)
                    with col2:
                        st.metric("Buying Power", f"${float(account.buying_power):,.2f}")
                    with col3:
                        st.metric("Equity", f"${float(account.equity):,.2f}")
                    
                except Exception as e:
                    st.error(f"❌ Connection failed: {e}")
        else:
            st.info("ℹ️ Add your API keys above to test the connection")
    
    with tab2:
        st.markdown("### 👤 Account Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Username**")
            st.text(user_data['username'])
        
        with col2:
            st.markdown("**Email**")
            st.text(user_data['email'])
        
        st.markdown("---")
        
        # Password change
        st.markdown("### 🔒 Change Password")
        
        with st.form("change_password_form"):
            current_password = st.text_input("Current Password", type="password")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm New Password", type="password")
            
            change_pwd = st.form_submit_button("Change Password", use_container_width=True)
            
            if change_pwd:
                if not all([current_password, new_password, confirm_password]):
                    st.warning("Please fill in all fields")
                elif new_password != confirm_password:
                    st.error("New passwords do not match")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    # Verify current password
                    user = db.authenticate_user(user_data['username'], current_password)
                    if user:
                        # Update password (would need to add this method to database.py)
                        st.info("Password change functionality coming soon")
                    else:
                        st.error("Current password is incorrect")
        
        st.markdown("---")
        
        # Danger zone
        st.markdown("### ⚠️ Danger Zone")
        
        with st.expander("Delete Account"):
            st.warning("⚠️ This action cannot be undone!")
            
            if st.button("Delete My Account", type="secondary"):
                st.error("Account deletion functionality coming soon. Please contact support.")
    
    with tab3:
        st.markdown("### 🎨 Trading Preferences")
        
        # Get current settings
        settings = db.get_all_settings(user_data['user_id'])
        
        with st.form("preferences_form"):
            # Auto-trade settings
            st.markdown("#### Auto-Trade Defaults")
            
            default_qty = st.number_input(
                "Default Trade Quantity",
                min_value=1,
                value=int(settings.get('default_quantity', 10)),
                help="Default number of shares for auto-trades"
            )
            
            stop_loss_pct = st.slider(
                "Stop Loss %",
                min_value=1,
                max_value=20,
                value=int(settings.get('stop_loss_pct', 5)),
                help="Automatic stop loss percentage"
            )
            
            take_profit_pct = st.slider(
                "Take Profit %",
                min_value=1,
                max_value=50,
                value=int(settings.get('take_profit_pct', 10)),
                help="Automatic take profit percentage"
            )
            
            st.markdown("#### Notifications")
            
            email_notifications = st.checkbox(
                "Email Notifications",
                value=settings.get('email_notifications', 'true') == 'true',
                help="Receive email alerts for trades"
            )
            
            trade_alerts = st.checkbox(
                "Trade Execution Alerts",
                value=settings.get('trade_alerts', 'true') == 'true',
                help="Get notified when trades are executed"
            )
            
            signal_alerts = st.checkbox(
                "Signal Alerts",
                value=settings.get('signal_alerts', 'true') == 'true',
                help="Get notified of buy/sell signals"
            )
            
            st.markdown("#### Display")
            
            theme = st.selectbox(
                "Dashboard Theme",
                ["Light", "Dark", "Auto"],
                index=["Light", "Dark", "Auto"].index(settings.get('theme', 'Auto'))
            )
            
            refresh_interval = st.slider(
                "Auto-refresh Interval (minutes)",
                min_value=1,
                max_value=60,
                value=int(settings.get('refresh_interval', 5)),
                help="How often to refresh data automatically"
            )
            
            save_prefs = st.form_submit_button("💾 Save Preferences", use_container_width=True)
            
            if save_prefs:
                # Save all settings
                db.save_setting(user_data['user_id'], 'default_quantity', str(default_qty))
                db.save_setting(user_data['user_id'], 'stop_loss_pct', str(stop_loss_pct))
                db.save_setting(user_data['user_id'], 'take_profit_pct', str(take_profit_pct))
                db.save_setting(user_data['user_id'], 'email_notifications', str(email_notifications).lower())
                db.save_setting(user_data['user_id'], 'trade_alerts', str(trade_alerts).lower())
                db.save_setting(user_data['user_id'], 'signal_alerts', str(signal_alerts).lower())
                db.save_setting(user_data['user_id'], 'theme', theme)
                db.save_setting(user_data['user_id'], 'refresh_interval', str(refresh_interval))
                
                st.success("✅ Preferences saved successfully!")
                st.rerun()
        
        st.markdown("---")
        
        # Export/Import settings
        st.markdown("### 📥 Data Management")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 Export Watchlist", use_container_width=True):
                watchlist = db.get_user_watchlist(user_data['user_id'])
                import pandas as pd
                df = pd.DataFrame(watchlist)
                csv = df.to_csv(index=False)
                st.download_button(
                    "Download Watchlist CSV",
                    csv,
                    file_name=f"watchlist_{user_data['username']}.csv",
                    mime="text/csv"
                )
        
        with col2:
            if st.button("📥 Export Trade History", use_container_width=True):
                trades = db.get_user_trades(user_data['user_id'], limit=10000)
                csv = trades.to_csv(index=False)
                st.download_button(
                    "Download Trades CSV",
                    csv,
                    file_name=f"trades_{user_data['username']}.csv",
                    mime="text/csv"
                )
    
    # Footer
    st.markdown("---")
    st.caption(f"SmartTrade Platform v1.0 | User ID: {user_data['user_id']}")
