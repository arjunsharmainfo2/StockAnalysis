"""
InvestmentFinderSystem: A class for filtering and analyzing stock universe based on technical criteria.
"""

import pandas as pd
from alpaca_trade_api.rest import REST, TimeFrame
from typing import List, Dict, Tuple
import yfinance as yf
from datetime import datetime


class InvestmentFinderSystem:
    """
    Investment Finder System for filtering stocks by technical indicators.
    
    Filters the universe of stocks based on volatility (ATR) and technical signals.
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str,
        tickers_universe: List[str],
        short_ma: int = 10,
        long_ma: int = 20,
        atr_period: int = 14
    ):
        """
        Initialize InvestmentFinderSystem.
        
        Args:
            api_key: Alpaca API key
            api_secret: Alpaca API secret
            base_url: Alpaca API base URL (e.g., https://paper-api.alpaca.markets)
            tickers_universe: List of ticker symbols to analyze
            short_ma: Period for short-term moving average (default 10)
            long_ma: Period for long-term moving average (default 20)
            atr_period: Period for ATR calculation (default 14)
        """
        self.api = REST(api_key, api_secret, base_url)
        self.tickers_universe = tickers_universe
        self.short_ma = short_ma
        self.long_ma = long_ma
        self.atr_period = atr_period
        self.filtered_universe = []
        self.atr_data = {}
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calculate Average True Range (ATR) for volatility measurement.
        
        ATR = mean of True Range over N periods
        True Range = max(High - Low, |High - Close_prev|, |Low - Close_prev|)
        
        Args:
            df: DataFrame with OHLC data (must have 'high', 'low', 'close')
            period: ATR period (default 14)
        
        Returns:
            Series of ATR values
        """
        high = df["high"]
        low = df["low"]
        close = df["close"]
        
        # Calculate True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Calculate ATR as rolling mean of TR
        atr = tr.rolling(window=period).mean()
        return atr
    
    def filter_universe(self, volatility_threshold: float = 0.05) -> Tuple[List[str], Dict[str, float]]:
        """
        Filter the universe by removing stocks with ATR > volatility_threshold * current_price.
        
        This removes excessively volatile stocks that could be risky for automated trading.
        
        Args:
            volatility_threshold: Maximum allowed ATR as a percentage of current price (default 0.05 = 5%)
        
        Returns:
            Tuple of (filtered_tickers, atr_ratios_dict)
            - filtered_tickers: List of tickers that passed the volatility filter
            - atr_ratios_dict: Dict mapping ticker to ATR/price ratio
        """
        self.filtered_universe = []
        self.atr_data = {}
        atr_ratios = {}
        
        for ticker in self.tickers_universe:
            try:
                # Fetch 30 daily bars (enough for 14-day ATR + buffers)
                bars = self.api.get_bars(ticker, TimeFrame.Day, limit=30).df
                
                if bars.empty or len(bars) < self.atr_period + 1:
                    print(f"{ticker}: Insufficient data for ATR calculation (need {self.atr_period + 1} bars)")
                    continue
                
                # Calculate ATR
                atr_series = self.calculate_atr(bars, period=self.atr_period)
                current_atr = atr_series.iloc[-1]
                current_price = bars["close"].iloc[-1]
                
                # Skip NaN ATR (happens in early periods)
                if pd.isna(current_atr) or pd.isna(current_price):
                    print(f"{ticker}: ATR or price is NaN, skipping")
                    continue
                
                # Calculate ATR as percentage of price
                atr_ratio = current_atr / current_price
                atr_ratios[ticker] = atr_ratio
                self.atr_data[ticker] = {
                    "atr": current_atr,
                    "price": current_price,
                    "atr_ratio": atr_ratio,
                    "passed": atr_ratio <= volatility_threshold
                }
                
                # Filter: keep only stocks with ATR <= threshold
                if atr_ratio <= volatility_threshold:
                    self.filtered_universe.append(ticker)
                    print(f"{ticker}: PASS (ATR: {current_atr:.2f}, Price: {current_price:.2f}, Ratio: {atr_ratio:.4f})")
                else:
                    print(f"{ticker}: FAIL (ATR: {current_atr:.2f}, Price: {current_price:.2f}, Ratio: {atr_ratio:.4f}) - TOO VOLATILE")
            
            except Exception as e:
                print(f"{ticker}: Error during filter -> {e}")
                continue
        
        print(f"\nFiltered Universe: {len(self.filtered_universe)}/{len(self.tickers_universe)} passed")
        return self.filtered_universe, atr_ratios
    
    def get_filtered_universe(self) -> List[str]:
        """Return the current filtered universe of tickers."""
        return self.filtered_universe
    
    def get_atr_data(self) -> Dict[str, Dict]:
        """Return ATR data for all analyzed tickers."""
        return self.atr_data
    
    def get_atr_summary_df(self) -> pd.DataFrame:
        """
        Return a DataFrame summary of ATR analysis for all tickers.
        
        Returns:
            DataFrame with columns: Ticker, ATR, Price, ATR_Ratio, Passed
        """
        rows = []
        for ticker, data in self.atr_data.items():
            rows.append({
                "Ticker": ticker,
                "ATR": round(data["atr"], 2),
                "Price": round(data["price"], 2),
                "ATR_Ratio": round(data["atr_ratio"], 4),
                "Passed": "Yes" if data["passed"] else "No"
            })
        return pd.DataFrame(rows)
    
    def generate_combined_signal(
        self,
        symbol: str,
        current_data: pd.DataFrame,
        yahoo_analysis: Dict
    ) -> Dict[str, any]:
        """
        Generate a combined technical + fundamental signal for a stock.
        
        Technical Signal:
        - BUY: MA10 > MA20 AND close > MA50
        - SELL: MA10 < MA20 AND close < MA50
        - HOLD: Otherwise
        
        Fundamental Confirmation (for BUY signals):
        - 'Strong Buy' or 'Outperform' → upgrade to 'STRONG BUY'
        - 'Hold' or 'Neutral' → downgrade to 'HOLD'
        - 'Sell' or 'Underperform' → downgrade to 'HOLD'
        
        Args:
            symbol: Ticker symbol
            current_data: DataFrame with OHLC data and MA10, MA20, MA50 columns
            yahoo_analysis: Dict with 'Summary' key containing analyst recommendation string
        
        Returns:
            Dict with keys:
            - 'signal': Final signal ('STRONG BUY', 'BUY', 'HOLD', 'SELL', 'STRONG SELL')
            - 'tech_signal': Pure technical signal
            - 'reason': Explanation of the signal
            - 'analyst_rec': Extracted analyst recommendation
        """
        
        if current_data is None or current_data.empty or len(current_data) < 50:
            return {
                "signal": "HOLD",
                "tech_signal": "HOLD",
                "reason": "Insufficient data for analysis",
                "analyst_rec": "N/A"
            }
        
        # Get latest data
        latest = current_data.iloc[-1]
        close = latest.get("close")
        
        # Calculate MA50 if not already in dataframe
        ma10 = latest.get("ma10")
        ma20 = latest.get("ma20")
        
        if "ma50" not in current_data.columns:
            current_data["ma50"] = current_data["close"].rolling(window=50).mean()
            ma50 = current_data["ma50"].iloc[-1]
        else:
            ma50 = latest.get("ma50")
        
        # Handle NaN values
        if pd.isna(ma10) or pd.isna(ma20) or pd.isna(ma50) or pd.isna(close):
            return {
                "signal": "HOLD",
                "tech_signal": "HOLD",
                "reason": "NaN values in MAs or close price",
                "analyst_rec": "N/A"
            }
        
        # Technical Signal
        if ma10 > ma20 and close > ma50:
            tech_signal = "BUY"
            tech_reason = f"MA10({ma10:.2f}) > MA20({ma20:.2f}) AND Close({close:.2f}) > MA50({ma50:.2f})"
        elif ma10 < ma20 and close < ma50:
            tech_signal = "SELL"
            tech_reason = f"MA10({ma10:.2f}) < MA20({ma20:.2f}) AND Close({close:.2f}) < MA50({ma50:.2f})"
        else:
            tech_signal = "HOLD"
            tech_reason = "No clear crossover pattern or price outside MA50 range"
        
        # Extract analyst recommendation from yahoo_analysis
        analyst_summary = yahoo_analysis.get("Summary", "").lower() if yahoo_analysis else ""
        
        # Fundamental confirmation logic
        final_signal = tech_signal
        fundamental_note = ""
        
        if tech_signal == "BUY":
            if "strong buy" in analyst_summary or "outperform" in analyst_summary:
                final_signal = "STRONG BUY"
                fundamental_note = " + Analyst: Strong Buy/Outperform"
            elif "hold" in analyst_summary or "neutral" in analyst_summary:
                final_signal = "HOLD"
                fundamental_note = " → Downgraded due to Hold/Neutral analyst recommendation"
            elif "sell" in analyst_summary or "underperform" in analyst_summary:
                final_signal = "HOLD"
                fundamental_note = " → Downgraded due to Sell/Underperform analyst recommendation"
        elif tech_signal == "SELL":
            # For SELL signals, only execute if analyst agrees
            if "sell" in analyst_summary or "underperform" in analyst_summary:
                final_signal = "STRONG SELL"
                fundamental_note = " + Analyst: Sell/Underperform"
            else:
                final_signal = "HOLD"
                fundamental_note = " → Downgraded; analyst doesn't support selling"
        
        reason = tech_reason + fundamental_note
        
        return {
            "signal": final_signal,
            "tech_signal": tech_signal,
            "reason": reason,
            "analyst_rec": analyst_summary if analyst_summary else "N/A"
        }
    
    def execute_trade(
        self,
        symbol: str,
        signal: str,
        entry_price: float,
        equity_to_risk: float = 500.0,
        risk_percent: float = 0.02
    ) -> Dict[str, any]:
        """
        Execute a trade with risk-managed bracket order for STRONG BUY signals.
        
        Risk Management:
        - qty = (equity_to_risk / risk_percent) / entry_price
        - Stop Loss: 5% below entry_price
        - Take Profit: 10% above entry_price
        
        Args:
            symbol: Ticker symbol to trade
            signal: Trading signal ('STRONG BUY', 'BUY', 'HOLD', etc.)
            entry_price: Current market price (entry point)
            equity_to_risk: Amount of equity willing to risk per trade (default $500)
            risk_percent: Risk as % of equity per trade (default 0.02 = 2%)
        
        Returns:
            Dict with keys:
            - 'success': Boolean indicating trade success
            - 'order_id': Order ID if successful
            - 'message': Status/error message
            - 'qty': Quantity executed (if successful)
            - 'entry': Entry price
            - 'stop_loss': Stop loss price
            - 'take_profit': Take profit price
        """
        
        # Only execute STRONG BUY signals
        if signal != "STRONG BUY":
            return {
                "success": False,
                "order_id": None,
                "message": f"Signal '{signal}' does not meet execution criteria (requires 'STRONG BUY')",
                "qty": 0,
                "entry": entry_price,
                "stop_loss": None,
                "take_profit": None
            }
        
        try:
            # Check if position already exists
            try:
                existing_position = self.api.get_position(symbol)
                if existing_position:
                    return {
                        "success": False,
                        "order_id": None,
                        "message": f"Position already exists for {symbol}. Skipping trade.",
                        "qty": 0,
                        "entry": entry_price,
                        "stop_loss": None,
                        "take_profit": None
                    }
            except Exception:
                # No position exists, continue
                pass
            
            # Calculate quantity based on risk management
            # qty = (equity_to_risk / risk_percent) / entry_price
            # This means: if we risk $500 at 2% risk, we can buy ($500/0.02)/entry_price shares
            qty = int((equity_to_risk / risk_percent) / entry_price)
            
            if qty <= 0:
                return {
                    "success": False,
                    "order_id": None,
                    "message": f"Calculated qty ({qty}) is invalid. Entry price too high relative to risk amount.",
                    "qty": qty,
                    "entry": entry_price,
                    "stop_loss": None,
                    "take_profit": None
                }
            
            # Calculate stop loss and take profit
            stop_loss_price = entry_price * 0.95  # 5% below entry
            take_profit_price = entry_price * 1.10  # 10% above entry
            
            # Submit bracket order
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side="buy",
                type="market",
                time_in_force="gtc",
                order_class="bracket",
                take_profit=dict(limit_price=round(take_profit_price, 2)),
                stop_loss=dict(stop_price=round(stop_loss_price, 2))
            )
            
            return {
                "success": True,
                "order_id": order.id,
                "message": f"✅ Bracket order submitted for {symbol}: {qty} shares @ ${entry_price:.2f}",
                "qty": qty,
                "entry": round(entry_price, 2),
                "stop_loss": round(stop_loss_price, 2),
                "take_profit": round(take_profit_price, 2)
            }
        
        except Exception as e:
            return {
                "success": False,
                "order_id": None,
                "message": f"❌ Error executing trade: {str(e)}",
                "qty": 0,
                "entry": entry_price,
                "stop_loss": None,
                "take_profit": None
            }
    
    def run_investment_finder(
        self,
        volatility_threshold: float = 0.05,
        equity_to_risk: float = 500.0,
        risk_percent: float = 0.02
    ) -> Dict[str, any]:
        """
        Orchestrate the entire investment finding and trading workflow.
        
        Workflow:
        1. Filter universe by volatility (ATR)
        2. For each filtered stock:
           a. Fetch latest technical data (daily bars)
           b. Fetch Yahoo fundamentals
           c. Generate combined signal (technical + fundamental)
           d. Execute trade if signal is STRONG BUY or SELL
        3. Return summary of all trades and analysis
        
        Args:
            volatility_threshold: ATR threshold for volatility filter (default 0.05 = 5%)
            equity_to_risk: Amount to risk per trade (default $500)
            risk_percent: Risk as % of equity (default 0.02 = 2%)
        
        Returns:
            Dict with:
            - 'timestamp': When the scan was run
            - 'filtered_universe': List of stocks that passed volatility filter
            - 'analysis_results': List of dicts with signal and trade results per stock
            - 'trades_executed': List of successful trades
            - 'summary': Text summary of performance
        """
        
        print(f"\n{'='*80}")
        print(f"INVESTMENT FINDER RUN - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
        
        # Step 1: Filter universe by volatility
        print("STEP 1: Filtering universe by volatility (ATR)...")
        filtered_stocks, atr_ratios = self.filter_universe(volatility_threshold=volatility_threshold)
        
        if not filtered_stocks:
            print("⚠️  No stocks passed volatility filter. Exiting.")
            return {
                "timestamp": datetime.now().isoformat(),
                "filtered_universe": [],
                "analysis_results": [],
                "trades_executed": [],
                "summary": "No stocks passed volatility filter."
            }
        
        print(f"✅ {len(filtered_stocks)} stocks passed volatility filter: {', '.join(filtered_stocks[:5])}{'...' if len(filtered_stocks) > 5 else ''}\n")
        
        # Step 2: Analyze and trade each stock
        analysis_results = []
        trades_executed = []
        
        print("STEP 2: Analyzing technical & fundamental data for each stock...\n")
        
        for symbol in filtered_stocks:
            print(f"Analyzing {symbol}...")
            try:
                # 2a. Fetch latest technical data (60 daily bars for MA50)
                bars = self.api.get_bars(symbol, TimeFrame.Day, limit=60).df
                
                if bars is None or len(bars) < 50:
                    print(f"  ⚠️  Insufficient data ({len(bars) if bars is not None else 0} bars). Skipping.\n")
                    continue
                
                # Calculate moving averages
                bars["ma10"] = bars["close"].rolling(window=10).mean()
                bars["ma20"] = bars["close"].rolling(window=20).mean()
                bars["ma50"] = bars["close"].rolling(window=50).mean()
                
                # 2b. Fetch Yahoo fundamentals
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    yahoo_analysis = {
                        "Summary": f"PE: {info.get('trailingPE', 'N/A')} | Market Cap: {info.get('marketCap', 'N/A')}"
                    }
                except Exception as e:
                    print(f"  ⚠️  Could not fetch Yahoo data: {e}")
                    yahoo_analysis = {"Summary": "N/A"}
                
                # 2c. Generate combined signal
                signal_result = self.generate_combined_signal(symbol, bars, yahoo_analysis)
                final_signal = signal_result["signal"]
                
                # Log the analysis
                entry_price = bars["close"].iloc[-1]
                result = {
                    "symbol": symbol,
                    "price": round(entry_price, 2),
                    "tech_signal": signal_result["tech_signal"],
                    "signal": final_signal,
                    "reason": signal_result["reason"],
                    "atr_ratio": round(atr_ratios.get(symbol, 0), 4)
                }
                analysis_results.append(result)
                
                print(f"  Signal: {final_signal} (Tech: {signal_result['tech_signal']})")
                print(f"  Price: ${entry_price:.2f}")
                print(f"  Reason: {signal_result['reason']}\n")
                
                # 2d. Execute trade if signal warrants
                if final_signal in ["STRONG BUY", "STRONG SELL"]:
                    print(f"  🎯 Executing trade for {symbol}...")
                    
                    # Map STRONG SELL to appropriate signal for execute_trade
                    trade_signal = "STRONG BUY" if final_signal == "STRONG BUY" else final_signal
                    
                    trade_result = self.execute_trade(
                        symbol=symbol,
                        signal=trade_signal,
                        entry_price=entry_price,
                        equity_to_risk=equity_to_risk,
                        risk_percent=risk_percent
                    )
                    
                    if trade_result["success"]:
                        print(f"  ✅ {trade_result['message']}")
                        trades_executed.append({
                            "symbol": symbol,
                            "signal": final_signal,
                            "qty": trade_result["qty"],
                            "entry": trade_result["entry"],
                            "stop_loss": trade_result["stop_loss"],
                            "take_profit": trade_result["take_profit"],
                            "order_id": trade_result["order_id"]
                        })
                    else:
                        print(f"  ❌ {trade_result['message']}\n")
                else:
                    print(f"  ⏸️  No trade signal. Signal={final_signal}\n")
            
            except Exception as e:
                print(f"  ❌ Error analyzing {symbol}: {e}\n")
                continue
        
        # Summary
        print(f"{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        print(f"Stocks Analyzed: {len(analysis_results)}")
        print(f"Trades Executed: {len(trades_executed)}")
        
        if trades_executed:
            print("\nExecuted Trades:")
            for trade in trades_executed:
                print(f"  • {trade['symbol']}: {trade['qty']} shares @ ${trade['entry']:.2f}")
                print(f"    SL: ${trade['stop_loss']:.2f} | TP: ${trade['take_profit']:.2f}")
        else:
            print("\nNo trades executed in this run.")
        
        summary_text = f"Analyzed {len(analysis_results)} stocks, executed {len(trades_executed)} trades."
        print(f"\n{summary_text}\n")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "filtered_universe": filtered_stocks,
            "analysis_results": analysis_results,
            "trades_executed": trades_executed,
            "summary": summary_text
        }

