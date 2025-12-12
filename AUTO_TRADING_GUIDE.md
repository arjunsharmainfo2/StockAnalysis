# Auto-Trading System - User Guide

## 🚀 Overview

The auto-trading system continuously monitors your watchlist and automatically executes trades based on CAN SLIM analysis. It checks your enabled stocks every **5 minutes** and makes intelligent buy/sell decisions using trend analysis, volume patterns, and technical indicators.

## ✨ Key Features

### 🎯 Intelligent Buying Strategy
- **Multi-Factor Scoring**: Analyzes 7+ factors to score each trading opportunity (0-10)
- **Golden Cross Detection**: Prioritizes stocks showing 50/200-day MA crossovers
- **Volume Breakouts**: Identifies unusual volume activity (>40% increase)
- **Relative Strength**: Tracks stocks with RS rating >80
- **Market Trend Alignment**: Only buys when market is in uptrend
- **Dynamic Position Sizing**: Adjusts position size based on signal strength

### 📊 Scoring System
The auto-trader scores each opportunity based on:
- Strong BUY signal with high confidence (2 points)
- Golden Cross detected (3 points)
- Price above both 50 & 200-day MAs (2 points)
- Volume breakout (2 points)
- Strong RS rating >80 (1 point)
- Market in uptrend (1 point)
- Multiple buy criteria met (2 points)

**Minimum score required: 5/10**

### 🛡️ Risk Management
- **Daily Trade Limits**: Set max trades per day (buys/sells separately)
- **Position Sizing**: Uses configurable % of buying power (5-20%)
- **Automatic Stop-Loss**: 8% below entry price
- **Automatic Take-Profit**: 10% above entry price
- **Bracket Orders**: Both stop and profit targets set on entry

## ⚙️ Configuration

### 1. Enable Auto-Trading for Stocks

Go to **Watchlist Manager** and toggle auto-trade for desired stocks:
```
Dashboard → Watchlist Manager → Toggle "Auto-Trade" column
```

### 2. Configure Settings

Navigate to **Settings → Auto-Trade** tab:

#### Trading Strategy
- **Minimum Confidence**: 50-95% (default: 70%)
  - Only trades when signal confidence meets threshold
  
- **Max Position Size**: 5-20% (default: 10%)
  - Maximum % of buying power per trade
  - Actual position may be smaller based on signal strength

#### Daily Limits
- **Max Total Trades/Day**: 1-100 (default: 20)
  - Combined buy and sell orders
  
- **Max Buys/Day**: 1-50 (default: 10)
  - Maximum new positions per day
  
- **Max Sells/Day**: 1-50 (default: 10)
  - Maximum positions closed per day

## 🏃 Running the Auto-Trader

### Option 1: Manual Execution (One-Time)
In the app, go to **Settings → Auto-Trade** and click:
```
🚀 Run Auto-Trade Now
```
This checks all enabled stocks once and executes any qualifying trades.

### Option 2: Continuous Execution (Recommended)

#### Using the Startup Script (Easy)
```bash
./start_auto_trader.sh <user_id> [interval_minutes]
```

Examples:
```bash
./start_auto_trader.sh 1        # Check every 5 minutes (default)
./start_auto_trader.sh 1 10     # Check every 10 minutes
```

#### Using Python Directly
```bash
python auto_trader.py <user_id> <interval_minutes>
```

Example:
```bash
python auto_trader.py 1 5  # User ID 1, check every 5 minutes
```

### Running in Background (macOS/Linux)
```bash
nohup ./start_auto_trader.sh 1 > auto_trader.log 2>&1 &
```

Check logs:
```bash
tail -f auto_trader.log
```

Stop background process:
```bash
pkill -f "python.*auto_trader.py"
```

## 📈 How It Works

### Every 5 Minutes:
1. **Check Daily Limits**: Ensures you haven't exceeded daily trade limits
2. **Load Enabled Stocks**: Gets all stocks with auto-trade enabled
3. **Analyze Each Stock**: Runs full CAN SLIM analysis
4. **Score Opportunity**: Calculates buy score (0-10)
5. **Execute Trades**:
   - **BUY**: If score ≥5 and no existing position
   - **SELL**: If sell signal and existing position
   - **HOLD**: If score <5 or already in position

### Buy Decision Logic:
```
IF signal = STRONG BUY or BUY
   AND confidence ≥ minimum threshold (70%)
   AND buy score ≥ 5
   AND daily buy limit not reached
   AND no existing position
THEN execute buy with position size based on score
```

### Sell Decision Logic:
```
IF signal = SELL
   AND has existing position
   AND daily sell limit not reached
THEN close entire position
```

## 📊 Monitoring

### Real-Time Logs
When running in terminal, you'll see:
```
🕐 Execution Time: 2025-12-12 15:30:00
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚙️  Settings: Min Confidence: 70% | Max Position: 10%
⚙️  Daily Limits: Total: 20 | Buys: 10 | Sells: 10
📊 Today's trades: 3 total (2 buys, 1 sells)
🔍 Checking 5 stocks for trading signals...

📊 Analyzing AAPL...
AAPL: STRONG BUY (Confidence: 85%)
💡 AAPL - Buy Strategy Score: 7/10
   Reasons: STRONG BUY signal with 85% confidence; Golden Cross detected; Price above 50 & 200-day MAs; Volume breakout (+45%)
🟢 AAPL: Buying 10 shares at ~$175.50 ($1755.00)
   Stop Loss: $161.46 | Take Profit: $193.05
✅ AAPL: Buy order submitted (Order ID: abc-123)
```

### In the App
- **Trade History**: View all executed auto-trades
- **Dashboard**: See current positions and P&L
- **Settings → Auto-Trade**: View today's trade count

## 🎛️ Advanced Configuration

### Position Sizing Strategy
Position size is dynamic based on signal strength:
```python
score = 7/10  # Example score
multiplier = min(score / 10, 1.0) = 0.7
position_pct = max_position_pct * multiplier
position_pct = 10% * 0.7 = 7%
```

### Custom Intervals
While 5 minutes is recommended, you can adjust:
- **1-2 minutes**: Very active (more API calls)
- **5 minutes**: Balanced (recommended)
- **10-15 minutes**: Conservative (fewer trades)

## ⚠️ Important Notes

### Limits & Safety
- Daily limits reset at midnight
- Trades are logged even if they fail
- System respects Alpaca API rate limits
- Bracket orders include automatic risk management

### Market Hours
- Auto-trader runs 24/7 but only trades during market hours
- Orders submitted outside hours execute at market open
- Consider stopping during extended holidays

### API Requirements
- Alpaca Paper Trading account (free)
- API keys configured in Settings
- Sufficient buying power for positions

## 🔧 Troubleshooting

### No Trades Executing
1. Check if stocks are enabled: `Watchlist Manager → Auto-Trade column`
2. Verify API keys: `Settings → API Keys`
3. Check daily limits: `Settings → Auto-Trade`
4. Review confidence threshold: May be too high

### Too Many Trades
1. Increase minimum confidence (70% → 80%)
2. Reduce daily trade limits
3. Disable some stocks in watchlist
4. Increase check interval (5 → 10 minutes)

### System Not Running
```bash
# Check if process is running
ps aux | grep auto_trader

# Check logs
tail -f auto_trader.log

# Restart
./start_auto_trader.sh 1 5
```

## 📚 Example Scenarios

### Conservative Trader
```
Min Confidence: 80%
Max Position Size: 5%
Max Daily Trades: 10
Max Daily Buys: 5
Max Daily Sells: 5
```

### Aggressive Trader
```
Min Confidence: 60%
Max Position Size: 15%
Max Daily Trades: 30
Max Daily Buys: 15
Max Daily Sells: 15
```

### Balanced Trader (Default)
```
Min Confidence: 70%
Max Position Size: 10%
Max Daily Trades: 20
Max Daily Buys: 10
Max Daily Sells: 10
```

## 🎯 Best Practices

1. **Start Small**: Begin with 2-3 stocks to test the system
2. **Monitor First Day**: Watch the logs for first 24 hours
3. **Adjust Gradually**: Tune settings based on performance
4. **Review Daily**: Check Trade History every evening
5. **Set Realistic Limits**: Don't exceed your risk tolerance
6. **Use Paper Trading**: Test thoroughly before going live

## 📞 Support

For issues or questions:
- Check logs: `auto_trader.log`
- Review trade history in app
- Verify settings in Settings → Auto-Trade

---

**Happy Trading! 🚀📈**
