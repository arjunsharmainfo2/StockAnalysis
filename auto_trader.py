"""
Auto-Trader - Automatically executes trades based on signals for enabled stocks
"""
import time
from datetime import datetime
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
    
    def check_and_execute_trades(self):
        """Check all auto-trade enabled stocks and execute trades based on signals"""
        # Get auto-trade enabled stocks
        watchlist = self.db.get_user_watchlist(self.user_id)
        auto_trade_stocks = [item for item in watchlist if item['auto_trade_enabled']]
        
        if not auto_trade_stocks:
            logger.info("No stocks enabled for auto-trading")
            return
        
        logger.info(f"Checking {len(auto_trade_stocks)} stocks for auto-trading...")
        
        for item in auto_trade_stocks:
            symbol = item['symbol']
            try:
                self.process_stock(symbol)
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
    
    def process_stock(self, symbol: str):
        """Process a single stock and execute trade if signal is strong"""
        logger.info(f"Analyzing {symbol}...")
        
        # Analyze stock
        analyzer = StockAnalyzer(symbol)
        result = analyzer.generate_signal()
        
        if result['signal'] == 'ERROR':
            logger.warning(f"Failed to analyze {symbol}")
            return
        
        signal = result['signal']
        confidence = result['confidence']
        
        logger.info(f"{symbol}: {signal} (Confidence: {confidence}%)")
        
        # Only trade on high confidence signals
        if confidence < 70:
            logger.info(f"{symbol}: Confidence too low, skipping")
            return
        
        # Get current position
        current_position = self.get_position(symbol)
        
        # Execute trade based on signal
        if signal in ['STRONG BUY', 'BUY']:
            if current_position == 0:
                self.execute_buy(symbol, result)
            else:
                logger.info(f"{symbol}: Already have position, skipping buy")
        
        elif signal == 'SELL':
            if current_position > 0:
                self.execute_sell(symbol, current_position)
            else:
                logger.info(f"{symbol}: No position to sell")
        
        else:  # HOLD
            logger.info(f"{symbol}: HOLD signal, no action")
    
    def get_position(self, symbol: str) -> int:
        """Get current position quantity for a symbol"""
        try:
            position = self.api.get_position(symbol)
            return int(position.qty)
        except:
            return 0
    
    def execute_buy(self, symbol: str, analysis: dict):
        """Execute a buy order with bracket orders"""
        try:
            # Get account buying power
            account = self.api.get_account()
            buying_power = float(account.buying_power)
            
            # Get current price from analysis
            price_data = analysis.get('analysis', {}).get('moving_averages', {})
            current_price = price_data.get('current_price', 0)
            
            if not current_price:
                logger.warning(f"{symbol}: Could not determine current price")
                return
            
            # Calculate position size (use 10% of buying power max)
            max_investment = buying_power * 0.10
            quantity = int(max_investment / current_price)
            
            if quantity < 1:
                logger.warning(f"{symbol}: Insufficient buying power for 1 share")
                return
            
            # Set stop loss (8% below) and take profit (10% above)
            stop_loss = round(current_price * 0.92, 2)
            take_profit = round(current_price * 1.10, 2)
            
            logger.info(f"{symbol}: Buying {quantity} shares at ~${current_price:.2f}")
            
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
                notes=f"Auto-trade: {analysis['signal']} ({analysis['confidence']}% confidence)"
            )
            
            logger.info(f"{symbol}: ✅ Buy order submitted (Order ID: {order.id})")
            
        except Exception as e:
            logger.error(f"{symbol}: Failed to execute buy: {e}")
    
    def execute_sell(self, symbol: str, quantity: int):
        """Execute a sell order"""
        try:
            logger.info(f"{symbol}: Selling {quantity} shares")
            
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
                notes="Auto-trade: SELL signal"
            )
            
            logger.info(f"{symbol}: ✅ Sell order submitted (Order ID: {order.id})")
            
        except Exception as e:
            logger.error(f"{symbol}: Failed to execute sell: {e}")


def run_auto_trader(user_id: int, interval_minutes: int = 15):
    """Run auto-trader continuously"""
    db = DatabaseManager()
    
    logger.info(f"Starting auto-trader for user {user_id} (interval: {interval_minutes} min)")
    
    while True:
        try:
            trader = AutoTrader(user_id, db)
            trader.check_and_execute_trades()
        except Exception as e:
            logger.error(f"Auto-trader error: {e}")
        
        # Wait for next interval
        logger.info(f"Waiting {interval_minutes} minutes until next check...")
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python auto_trader.py <user_id> [interval_minutes]")
        sys.exit(1)
    
    user_id = int(sys.argv[1])
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    
    run_auto_trader(user_id, interval)
