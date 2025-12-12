# SmartTrade Platform - SaaS Trading Application

A full-featured SaaS (Software as a Service) trading platform with user authentication, personalized watchlists, automated trading, and comprehensive stock analysis.

## 🚀 Features

### User Management
- **Secure Authentication**: User registration and login with password hashing
- **Personal Accounts**: Each user has their own isolated trading environment
- **API Key Management**: Securely store Alpaca API credentials per user

### Stock Analysis
- **1-Week Technical Analysis**: Candlestick charts, RSI, Moving Averages
- **News Sentiment**: Real-time news aggregation with sentiment scoring
- **AI-Powered Signals**: Buy/Sell/Hold recommendations based on technical + news data
- **Interactive Charts**: Plotly-powered visualizations

### Trading Features
- **Personalized Watchlists**: Add/remove stocks, manage multiple symbols
- **Auto-Trading**: Enable automated trading per stock
- **Alpaca Integration**: Execute real trades with bracket orders (stop-loss & take-profit)
- **Trade History**: Complete log of all trades with P&L tracking

### Dashboard
- **Summary View**: Quick overview of all watchlist stocks
- **Click-Through Navigation**: Click any stock to view detailed analysis
- **Performance Metrics**: Win rate, P&L, trade count
- **Auto-Refresh**: Configurable refresh intervals

## 📁 Project Structure

```
Finance Work/
├── app.py                      # Main application entry point
├── database.py                 # Database manager (SQLite)
├── pages/                      # Multi-page modules
│   ├── __init__.py
│   ├── dashboard.py           # Main dashboard with stock summary
│   ├── stock_details.py       # Detailed stock analysis & trading
│   ├── watchlist_manager.py   # Add/remove stocks, auto-trade settings
│   ├── trade_history.py       # Trade log and P&L analytics
│   └── settings.py            # User preferences and API keys
├── trading_platform.db         # SQLite database (created on first run)
├── requirements.txt            # Python dependencies
└── README_SAAS.md             # This file
```

## 🗄️ Database Schema

### Tables
- **users**: User accounts with encrypted passwords
- **watchlists**: User-specific stock watchlists
- **trades**: Complete trade history
- **trading_sessions**: Track trading sessions
- **user_settings**: Personalized preferences
- **analysis_cache**: Performance optimization

## 🔧 Installation

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application**:
   ```bash
   streamlit run app.py
   ```

3. **Access in browser**:
   - Open http://localhost:8501
   - Register a new account
   - Configure API keys in Settings

## 👤 Getting Started

### 1. Create Account
- Click "Register" tab
- Enter username, email, and password
- Click "Register"

### 2. Configure API Keys
- Go to **Settings** → **API Keys**
- Get keys from [Alpaca Markets](https://alpaca.markets/)
- Enter API Key ID and Secret
- Select Paper Trading for testing
- Click "Test Connection"

### 3. Add Stocks to Watchlist
- Go to **Watchlist Manager**
- Enter stock symbols (comma-separated)
- Enable/disable auto-trading per stock
- Or use "Popular Stocks" quick-add buttons

### 4. View Dashboard
- Go to **Dashboard**
- See all stocks with real-time data
- Click any stock to view details

### 5. Analyze & Trade
- Click stock symbol in Dashboard
- View detailed charts, news, and analysis
- Execute manual trades from **Trade** tab
- View trade history in **Trade History**

## 🔐 Security Features

- **Password Hashing**: PBKDF2-SHA256 with salt
- **Session Management**: Secure session state
- **API Key Encryption**: Stored securely in database
- **User Isolation**: Each user's data is completely isolated

## 📊 Key Pages

### Dashboard
- Summary table of all watchlist stocks
- Quick metrics: price, week change, signal
- Click-through to stock details
- Remove stocks directly
- Compare multiple stocks with charts

### Stock Details
- **Charts Tab**: Candlestick, volume, RSI charts
- **News Tab**: Latest news with sentiment
- **Info Tab**: Company fundamentals
- **Trade Tab**: Execute buy/sell orders
- Trade history for specific stock

### Watchlist Manager
- Add multiple stocks at once
- Toggle auto-trade per stock
- Bulk actions (enable/disable all)
- Popular stocks suggestions by category

### Trade History
- Complete trade log
- Filter by symbol, action, side
- P&L analytics and charts
- Win rate calculation
- Download CSV export

### Settings
- **API Keys**: Configure Alpaca credentials
- **Account**: Update password, account info
- **Preferences**: Trading defaults, notifications, theme

## 🤖 Auto-Trading

Enable auto-trading for specific stocks:
1. Go to **Watchlist Manager**
2. Check "Auto-Trade" for desired stocks
3. Auto-trade uses default settings from **Settings** → **Preferences**
4. Bracket orders with stop-loss (5%) and take-profit (10%)

## 📈 Analysis Features

### Technical Indicators
- **MA5, MA10, MA20**: Moving averages
- **RSI**: Relative Strength Index (14-period)
- **Volume Analysis**: Volume vs moving average
- **Candlestick Patterns**: Visual price action

### Signal Generation
- **Technical Signal**: Based on MA crossovers and RSI
- **News Signal**: Sentiment analysis from headlines
- **Combined Signal**: Final recommendation (STRONG BUY/SELL/HOLD)
- **Confidence Level**: HIGH/MEDIUM/LOW

## 🔄 Continuous Trading

The platform supports continuous trading:
- Stocks in watchlist are continuously monitored
- Auto-trade enabled stocks execute based on signals
- All trades are logged to database
- Performance tracked in Trade History

## 💡 Tips

1. **Start with Paper Trading**: Use paper-api.alpaca.markets for testing
2. **Enable Auto-Trade Gradually**: Start with 1-2 stocks
3. **Monitor Trade History**: Check P&L regularly
4. **Adjust Settings**: Customize stop-loss and take-profit %
5. **Use News Tab**: Check sentiment before manual trades

## 🚨 Troubleshooting

### "API credentials not set"
- Go to Settings → API Keys
- Enter valid Alpaca API keys
- Test connection

### "No data available"
- Check internet connection
- Verify stock symbol is valid
- Market may be closed (Yahoo Finance data available 24/7)

### Trades not executing
- Verify API keys are correct
- Check Alpaca account status
- Ensure sufficient buying power

## 🆚 Differences from bot_dashboard.py

| Feature | bot_dashboard.py | app.py (SaaS) |
|---------|------------------|---------------|
| Users | Single user | Multi-user with auth |
| Data Storage | CSV files | SQLite database |
| Watchlist | Hardcoded | User-specific, persistent |
| Navigation | Single page | Multi-page app |
| Trade History | CSV logs | Database with analytics |
| API Keys | Environment vars | Per-user in database |
| Settings | Hardcoded | Customizable per user |
| Continuous Trading | Manual script run | Built-in sessions |

## 📦 Technologies

- **Streamlit**: Web framework
- **SQLite**: Database
- **Pandas**: Data processing
- **Plotly**: Interactive charts
- **yfinance**: Stock data
- **Alpaca Trade API**: Trading execution
- **PBKDF2**: Password hashing

## 🔜 Future Enhancements

- Email notifications
- Portfolio tracking
- Multi-factor authentication
- Mobile responsive design
- Backtesting engine
- Social trading features
- Advanced charting tools

## 📝 License

For personal and educational use.

---

**Made with ❤️ for traders**
