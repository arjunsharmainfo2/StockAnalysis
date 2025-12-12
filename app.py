"""
Main Application Entry Point - Multi-page SaaS Trading Platform
"""
import streamlit as st
from database import DatabaseManager
from datetime import datetime, timedelta

# Import all pages at module level
import pages.dashboard as dashboard
import pages.stock_details as stock_details
import pages.watchlist_manager as watchlist_manager
import pages.trade_history as trade_history
import pages.settings as settings

# Page configuration
st.set_page_config(
    page_title="SmartTrade Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
if 'db' not in st.session_state:
    st.session_state.db = DatabaseManager()

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_data' not in st.session_state:
    st.session_state.user_data = None
if 'last_activity' not in st.session_state:
    st.session_state.last_activity = datetime.now()

# Session timeout configuration (30 minutes)
SESSION_TIMEOUT_MINUTES = 30

def check_session_timeout():
    """Check if session has timed out due to inactivity"""
    if st.session_state.logged_in:
        current_time = datetime.now()
        time_diff = current_time - st.session_state.last_activity
        
        # Check if inactive for more than 30 minutes
        if time_diff > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            st.session_state.logged_in = False
            st.session_state.user_data = None
            st.warning(f"⏰ Session expired due to {SESSION_TIMEOUT_MINUTES} minutes of inactivity. Please log in again.")
            return True
    return False

def update_activity():
    """Update last activity timestamp"""
    st.session_state.last_activity = datetime.now()

def login_page():
    """Login/Registration page"""
    st.title("📈 SmartTrade Platform")
    st.markdown("### AI-Powered Stock Trading & Analysis")
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.subheader("Login to Your Account")
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login", use_container_width=True)
            
            if submit:
                if username and password:
                    user_data = st.session_state.db.authenticate_user(username, password)
                    
                    if user_data:
                        st.session_state.logged_in = True
                        st.session_state.user_data = user_data
                        st.session_state.last_activity = datetime.now()  # Set initial activity time
                        st.success(f"Welcome back, {username}!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
                else:
                    st.warning("Please enter both username and password")
    
    with tab2:
        st.subheader("Create New Account")
        
        with st.form("register_form"):
            new_username = st.text_input("Choose Username")
            new_email = st.text_input("Email Address")
            new_password = st.text_input("Choose Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            register = st.form_submit_button("Register", use_container_width=True)
            
            if register:
                if not all([new_username, new_email, new_password, confirm_password]):
                    st.warning("Please fill in all fields")
                elif new_password != confirm_password:
                    st.error("Passwords do not match")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    success = st.session_state.db.create_user(
                        new_username, new_email, new_password
                    )
                    
                    if success:
                        st.success("Account created successfully! Please login.")
                    else:
                        st.error("Username or email already exists")
    
    # Info section
    st.markdown("---")
    st.markdown("""
    ### Features
    - 📊 Real-time stock analysis with Yahoo Finance
    - 🤖 AI-powered buy/sell signals
    - 📰 News sentiment analysis
    - 💰 Automated trading with Alpaca
    - 📈 1-week technical analysis with candlestick charts
    - 🎯 Personalized watchlist management
    """)

def main_app():
    """Main application with navigation"""
    
    # Check for session timeout
    if check_session_timeout():
        st.rerun()
        return
    
    # Update last activity timestamp
    update_activity()
    
    # Calculate remaining session time
    time_since_activity = datetime.now() - st.session_state.last_activity
    remaining_minutes = SESSION_TIMEOUT_MINUTES - int(time_since_activity.total_seconds() / 60)
    
    # Sidebar navigation
    with st.sidebar:
        st.title("📈 SmartTrade")
        st.markdown(f"**Welcome, {st.session_state.user_data['username']}!**")
        
        # Session info
        if remaining_minutes < 5:
            st.warning(f"⏰ Session expires in {remaining_minutes} min")
            if st.button("🔄 Extend Session", use_container_width=True):
                st.session_state.last_activity = datetime.now()
                st.success("Session extended!")
                st.rerun()
        else:
            st.caption(f"🕐 Session active ({remaining_minutes} min remaining)")
        
        st.markdown("---")
        
        # Navigation
        page = st.radio(
            "Navigate to:",
            ["Dashboard", "Stock Details", "Watchlist Manager", "Trade History", "Settings", "Logout"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.caption(f"User ID: {st.session_state.user_data['user_id']}")
    
    # Route to appropriate page (outside sidebar context!)
    if page == "Logout":
        st.session_state.logged_in = False
        st.session_state.user_data = None
        st.session_state.last_activity = None
        st.info("✅ Logged out successfully")
        st.rerun()
    elif page == "Dashboard":
        dashboard.show(st.session_state.user_data, st.session_state.db)
    elif page == "Stock Details":
        stock_details.show(st.session_state.user_data, st.session_state.db)
    elif page == "Watchlist Manager":
        watchlist_manager.show(st.session_state.user_data, st.session_state.db)
    elif page == "Trade History":
        trade_history.show(st.session_state.user_data, st.session_state.db)
    elif page == "Settings":
        settings.show(st.session_state.user_data, st.session_state.db)
    
    # Auto-refresh every 60 seconds to check session timeout
    import time
    time.sleep(0.1)  # Small delay to prevent excessive reruns

# Main execution
if not st.session_state.logged_in:
    login_page()
else:
    main_app()
