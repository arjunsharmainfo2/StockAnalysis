"""
Auto-Trader - Automatically executes trades based on signals for enabled stocks
Runs continuously every 5 minutes with daily trade limits
"""
import time
from datetime import datetime, timedelta
from database import DatabaseManager
from stock_analyzer import StockAnalyzer
from alpaca_trade_api.rest import REST
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutoTrader:
    def __init__(self, user_id: int, db: DatabaseManager):
        self.user_id = user_id
        self.db = db
        self.api_key, self.api_secret = db.get_user_api_keys(user_id)
        
        if not self.api_key or not self.api_secret:
            raise ValueError("API keys not configured")
        
        self.api = REST(self.api_key, self.api_secret, "https://paper-api.alpaca.markets")
        
        # Load user settings
        self.min_confidence = int(db.get_setting(user_id, 'auto_trade_min_confidence') or 70)
        self.max_position_pct = int(db.get_setting(user_id, 'auto_trade_max_position_pct') or 10)
        self.max_daily_trades = int(db.get_setting(user_id, 'auto_trade_max_daily_trades') or 20)
        self.max_daily_buys = int(db.get_setting(user_id, 'auto_trade_max_daily_buys') or 10)
        self.max_daily_sells = int(db.get_setting(user_id, 'auto_trade_max_daily_sells') or 10)
    
    def get_today_trade_count(self) -> dict:
        """Get count of trades executed today"""
        trades_df = self.db.get_user_trades(self.user_id, limit=1000)
        
        if trades_df.empty:
            return {'total': 0, 'buys': 0, 'sells': 0}
        
        # Filter for today's trades
        today = datetime.now().date()
        trades_df['trade_date'] = trades_df['executed_at'].apply(lambda x: datetime.fromisoformat(x).date())
        today_trades = trades_df[trades_df['trade_date'] == today]
        
        return {
            'total': len(today_trades),
            'buys': len(today_trades[today_trades['side'] == 'BUY']),
            'sells': len(today_trades[today_trades['side'] == 'SELL'])
        }
    
    def check_daily_limits(self, action: str) -> bool:
        """Check if daily trading limits have been reached"""
        counts = self.get_today_trade_count()
        
        if counts['total'] >= self.max_daily_trades:
            logger.warning(f"Daily trade limit reached ({counts['total']}/{self.max_daily_trades})")
            return False
        
        if action == 'BUY' and counts['buys'] >= self.max_daily_buys:
            logger.warning(f"Daily buy limit reached ({counts['buys']}/{self.max_daily_buys})")
            return False
        
        if action == 'SELL' and counts['sells'] >= self.max_daily_sells:
            logger.warning(f"Daily sell limit reached ({counts['sells']}/{self.max_daily_sells})")
            return False
        
        return True
    
    def check_and_execute_trades(self):
        """Check all auto-trade enabled stocks and execute trades based on signals"""
        # Check daily limits
        counts = self.get_today_trade_count()
        logger.info(f"📊 Today's trades: {counts['total']} total ({counts['buys']} buys, {counts['sells']} sells)")
        
        if counts['total'] >= self.max_daily_trades:
            logger.warning("⚠️ Daily trade limit reached, skipping execution")
            return
        
        # Get auto-trade enabled stocks
        watchlist = self.db.get_user_watchlist(self.user_id)
        auto_trade_stocks = [item for item in watchlist if item['auto_trade_enabled']]
        
        if not auto_trade_stocks:
            logger.info("No stocks enabled for auto-trading")
            return
        
        logger.info(f"🔍 Checking {len(auto_trade_stocks)} stocks for trading signals...")
        
        for item in auto_trade_stocks:
            symbol = item['symbol']
            try:
                self.process_stock(symbol)
            except Exception as e:
                logger.error(f"❌ Error processing {symbol}: {e}")
    
    def analyze_buying_strategy(self, symbol: str, analysis: dict) -> dict:
        """
        Enhanced buying strategy based on multiple factors
        Returns: {'should_buy': bool, 'quantity': int, 'reason': str}
        """
        signal = analysis['signal']
        confidence = analysis['confidence']
        buy_criteria = analysis.get('buy_criteria_met', {})
        
        # Get detailed analysis
        ma_data = analysis.get('analysis', {}).get('moving_averages', {})
        volume_data = analysis.get('analysis', {}).get('volume', {})
        rs_data = analysis.get('analysis', {}).get('relative_strength', {})
        market_data = analysis.get('analysis', {}).get('market_trend', {})
        
        # Score the opportunity
        score = 0
        reasons = []
        
        # 1. Strong signal and confidence
        if signal in ['STRONG BUY', 'BUY'] and confidence >= self.min_confidence:
            score += 2
            reasons.append(f"{signal} signal with {confidence}% confidence")
        else:
            return {'should_buy': False, 'quantity': 0, 'reason': 'Weak signal or low confidence'}
        
        # 2. Golden Cross is very bullish
        if ma_data.get('golden_cross'):
            score += 3
            reasons.append("Golden Cross detected")
        
        # 3. Price above both MAs
        if ma_data.get('above_50') and ma_data.get('above_200'):
            score += 2
            reasons.append("Price above 50 & 200-day MAs")
        
        # 4. Volume breakout
        if volume_data.get('breakout'):
            score += 2
            reasons.append(f"Volume breakout (+{volume_data.get('volume_increase_pct', 0):.0f}%)")
        
        # 5. Strong relative strength
        if rs_data.get('meets_criteria'):
            score += 1
            reasons.append("Strong RS rating (>80)")
        
        # 6. Market in uptrend
        if market_data.get('uptrend'):
            score += 1
            reasons.append("Market in uptrend")
        
        # 7. All buy criteria met
        criteria_met = sum(buy_criteria.values())
        if criteria_met >= 3:
            score += 2
            reasons.append(f"Buy criteria: {criteria_met}/4")
        
        # Determine if we should buy (score >= 5 is good opportunity)
        if score >= 5:
            # Calculate position size based on score
            # Higher score = larger position (up to max_position_pct)
            position_multiplier = min(score / 10, 1.0)  # Max 1.0
            position_pct = self.max_position_pct * position_multiplier
            
            return {
                'should_buy': True,
                'position_pct': position_pct,
                'score': score,
                'reason': '; '.join(reasons)
            }
        else:
            return {
                'should_buy': False,
                'quantity': 0,
                'reason': f"Score too low ({score}/10)"
            }
    
    def process_stock(self, symbol: str):
        """Process a single stock and execute trade if signal is strong"""
        logger.info(f"📊 Analyzing {symbol}...")
        
        # Analyze stock
        analyzer = StockAnalyzer(symbol)
        result = analyzer.generate_signal()
        
        if result['signal'] == 'ERROR':
            logger.warning(f"⚠️ Failed to analyze {symbol}")
            return
        
        signal = result['signal']
        confidence = result['confidence']
        
        logger.info(f"{symbol}: {signal} (Confidence: {confidence}%)")
        
        # Get current position
        current_position = self.get_position(symbol)
        
        # Execute trade based on signal
        if signal in ['STRONG BUY', 'BUY']:
            if current_position == 0:
                # Analyze if we should buy
                strategy = self.analyze_buying_strategy(symbol, result)
                
                if strategy['should_buy']:
                    if self.check_daily_limits('BUY'):
                        logger.info(f"💡 {symbol} - Buy Strategy Score: {strategy['score']}/10")
                        logger.info(f"   Reasons: {strategy['reason']}")
                        self.execute_buy(symbol, result, strategy['position_pct'])
                    else:
                        logger.info(f"⏸️ {symbol}: Buy signal but daily limit reached")
                else:
                    logger.info(f"⏸️ {symbol}: {strategy['reason']}")
            else:
                logger.info(f"✋ {symbol}: Already have position ({current_position} shares)")
        
        elif signal == 'SELL':
            if current_position > 0:
                if self.check_daily_limits('SELL'):
                    logger.info(f"🔴 {symbol}: SELL signal - closing position")
                    self.execute_sell(symbol, current_position, result['reason'])
                else:
                    logger.info(f"⏸️ {symbol}: Sell signal but daily limit reached")
            else:
                logger.info(f"👍 {symbol}: SELL signal but no position to close")
        
        else:  # HOLD
            if current_position > 0:
                logger.info(f"🟡 {symbol}: HOLD - maintaining position ({current_position} shares)")
            else:
                logger.info(f"🟡 {symbol}: HOLD - watching for better entry")
    
    def get_position(self, symbol: str) -> int:
        """Get current position quantity for a symbol"""
        try:
            position = self.api.get_position(symbol)
            return int(position.qty)
        except:
            return 0
    
    def execute_buy(self, symbol: str, analysis: dict, position_pct: float):
        """Execute a buy order with bracket orders"""
        try:
            # Get account buying power
            account = self.api.get_account()
            buying_power = float(account.buying_power)
            
            # Get current price from analysis
            price_data = analysis.get('analysis', {}).get('moving_averages', {})
            current_price = price_data.get('current_price', 0)
            
            if not current_price:
                logger.warning(f"⚠️ {symbol}: Could not determine current price")
                return
            
            # Calculate position size
            max_investment = buying_power * (position_pct / 100)
            quantity = int(max_investment / current_price)
            
            if quantity < 1:
                logger.warning(f"⚠️ {symbol}: Insufficient buying power for 1 share")
                return
            
            # Set stop loss (8% below) and take profit (10% above)
            stop_loss = round(current_price * 0.92, 2)
            take_profit = round(current_price * 1.10, 2)
            
            logger.info(f"🟢 {symbol}: Buying {quantity} shares at ~${current_price:.2f} (${max_investment:.2f})")
            logger.info(f"   Stop Loss: ${stop_loss} | Take Profit: ${take_profit}")
            
            order = self.api.submit_order(
                symbol=symbol,
                qty=quantity,
                side="buy",
                type="market",
                time_in_force="gtc",
                order_class="bracket",
                take_profit=dict(limit_price=take_profit),
                stop_loss=dict(stop_price=stop_loss)
            )
            
            # Log trade
            self.db.log_trade(
                user_id=self.user_id,
                symbol=symbol,
                action="OPEN",
                side="BUY",
                quantity=quantity,
                price=current_price,
                order_id=order.id,
                notes=f"Auto-trade: {analysis['signal']} ({analysis['confidence']}% confidence) | Score: {int(position_pct * 10)}/10"
            )
            
            logger.info(f"✅ {symbol}: Buy order submitted (Order ID: {order.id})")
            
        except Exception as e:
            logger.error(f"❌ {symbol}: Failed to execute buy: {e}")
    
    def execute_sell(self, symbol: str, quantity: int, reason: str):
        """Execute a sell order"""
        try:
            logger.info(f"🔴 {symbol}: Selling {quantity} shares - {reason}")
            
            order = self.api.submit_order(
                symbol=symbol,
                qty=quantity,
                side="sell",
                type="market",
                time_in_force="gtc"
            )
            
            # Get execution price (approximate with current market price)
            try:
                latest_quote = self.api.get_latest_trade(symbol)
                price = latest_quote.price
            except:
                price = 0
            
            # Log trade
            self.db.log_trade(
                user_id=self.user_id,
                symbol=symbol,
                action="CLOSE",
                side="SELL",
                quantity=quantity,
                price=price,
                order_id=order.id,
                notes=f"Auto-trade: SELL signal - {reason}"
            )
            
            logger.info(f"✅ {symbol}: Sell order submitted (Order ID: {order.id})")
            
        except Exception as e:
            logger.error(f"❌ {symbol}: Failed to execute sell: {e}")


def run_auto_trader(user_id: int, interval_minutes: int = 5):
    """Run auto-trader continuously with 5-minute intervals"""
    db = DatabaseManager()
    
    logger.info(f"🚀 Starting continuous auto-trader for user {user_id}")
    logger.info(f"⏱️  Check interval: {interval_minutes} minutes")
    logger.info(f"=" * 60)
    
    while True:
        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"\n{'=' * 60}")
            logger.info(f"🕐 Execution Time: {current_time}")
            logger.info(f"{'=' * 60}")
            
            trader = AutoTrader(user_id, db)
            
            # Show current settings
            logger.info(f"⚙️  Settings: Min Confidence: {trader.min_confidence}% | Max Position: {trader.max_position_pct}%")
            logger.info(f"⚙️  Daily Limits: Total: {trader.max_daily_trades} | Buys: {trader.max_daily_buys} | Sells: {trader.max_daily_sells}")
            
            trader.check_and_execute_trades()
            
        except Exception as e:
            logger.error(f"❌ Auto-trader error: {e}")
        
        # Wait for next interval
        next_run = datetime.now() + timedelta(minutes=interval_minutes)
        logger.info(f"\n⏳ Next check at {next_run.strftime('%H:%M:%S')}")
        logger.info(f"{'=' * 60}\n")
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python auto_trader.py <user_id> [interval_minutes]")
        print("Example: python auto_trader.py 1 5")
        sys.exit(1)
    
    user_id = int(sys.argv[1])
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    run_auto_trader(user_id, interval)
