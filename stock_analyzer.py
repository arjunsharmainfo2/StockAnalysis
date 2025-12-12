"""
Advanced Stock Analyzer - CAN SLIM Style Analysis
Implements comprehensive buy/sell/hold criteria based on fundamental and technical analysis
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional

class StockAnalyzer:
    """
    Analyzes stocks using CAN SLIM methodology
    """
    
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self.ticker = yf.Ticker(self.symbol)
        self.data = None
        self.info = None
        
    def fetch_data(self, period="1y") -> bool:
        """Fetch historical data and stock info"""
        try:
            self.data = self.ticker.history(period=period)
            self.info = self.ticker.info
            return not self.data.empty
        except Exception as e:
            print(f"Error fetching data for {self.symbol}: {e}")
            return False
    
    # ============= FUNDAMENTAL ANALYSIS =============
    
    def check_eps_growth(self) -> Dict:
        """
        Check EPS growth - target >25% YoY
        Returns: {'current_eps': float, 'yoy_growth': float, 'meets_criteria': bool}
        """
        try:
            # Get quarterly earnings
            earnings = self.ticker.quarterly_earnings
            if earnings is None or len(earnings) < 5:
                return {'current_eps': None, 'yoy_growth': None, 'meets_criteria': False, 'error': 'Insufficient data'}
            
            # Compare most recent quarter with same quarter last year (4 quarters ago)
            current_eps = earnings.iloc[0]['Earnings'] if 'Earnings' in earnings.columns else None
            year_ago_eps = earnings.iloc[4]['Earnings'] if len(earnings) > 4 and 'Earnings' in earnings.columns else None
            
            if current_eps and year_ago_eps and year_ago_eps != 0:
                yoy_growth = ((current_eps - year_ago_eps) / abs(year_ago_eps)) * 100
                return {
                    'current_eps': current_eps,
                    'year_ago_eps': year_ago_eps,
                    'yoy_growth': yoy_growth,
                    'meets_criteria': yoy_growth >= 25.0
                }
        except Exception as e:
            pass
        
        # Fallback to annual EPS from info
        try:
            trailing_eps = self.info.get('trailingEps', 0)
            forward_eps = self.info.get('forwardEps', 0)
            
            if trailing_eps and forward_eps and trailing_eps > 0:
                growth = ((forward_eps - trailing_eps) / trailing_eps) * 100
                return {
                    'current_eps': forward_eps,
                    'yoy_growth': growth,
                    'meets_criteria': growth >= 25.0
                }
        except Exception:
            pass
            
        return {'current_eps': None, 'yoy_growth': None, 'meets_criteria': False}
    
    def check_annual_growth(self) -> Dict:
        """
        Check 3-year earnings growth history - target >25% per year
        """
        try:
            # Get annual earnings
            financials = self.ticker.financials
            if financials is None or len(financials.columns) < 3:
                return {'avg_growth': None, 'meets_criteria': False}
            
            # Get net income for past 3 years
            if 'Net Income' in financials.index:
                net_income = financials.loc['Net Income']
                if len(net_income) >= 3:
                    # Calculate year-over-year growth rates
                    growth_rates = []
                    for i in range(min(3, len(net_income)-1)):
                        if net_income.iloc[i] != 0 and net_income.iloc[i+1] != 0:
                            growth = ((net_income.iloc[i] - net_income.iloc[i+1]) / abs(net_income.iloc[i+1])) * 100
                            growth_rates.append(growth)
                    
                    if growth_rates:
                        avg_growth = np.mean(growth_rates)
                        return {
                            'avg_growth': avg_growth,
                            'growth_rates': growth_rates,
                            'meets_criteria': avg_growth >= 25.0
                        }
        except Exception:
            pass
        
        return {'avg_growth': None, 'meets_criteria': False}
    
    def check_pe_ratio(self) -> Dict:
        """
        Compare P/E ratio to industry average
        """
        try:
            pe_ratio = self.info.get('trailingPE', None) or self.info.get('forwardPE', None)
            industry_pe = self.info.get('industryPE', None)
            sector = self.info.get('sector', 'Unknown')
            
            # Default industry P/E ratios
            default_industry_pe = {
                'Technology': 35,
                'Healthcare': 25,
                'Financial Services': 15,
                'Consumer Cyclical': 20,
                'Communication Services': 25,
                'Industrials': 20,
                'Consumer Defensive': 22,
                'Energy': 15,
                'Utilities': 18,
                'Real Estate': 30,
                'Basic Materials': 18
            }
            
            if not industry_pe:
                industry_pe = default_industry_pe.get(sector, 20)
            
            if pe_ratio and industry_pe:
                undervalued = pe_ratio < industry_pe
                discount_pct = ((industry_pe - pe_ratio) / industry_pe) * 100 if undervalued else 0
                
                return {
                    'pe_ratio': pe_ratio,
                    'industry_pe': industry_pe,
                    'sector': sector,
                    'undervalued': undervalued,
                    'discount_pct': discount_pct,
                    'meets_criteria': undervalued
                }
        except Exception:
            pass
        
        return {'pe_ratio': None, 'meets_criteria': False}
    
    def check_peg_ratio(self) -> Dict:
        """
        Check PEG ratio - target <1.0 for undervalued growth stocks
        """
        try:
            peg_ratio = self.info.get('pegRatio', None)
            
            # Calculate PEG manually if not available
            if not peg_ratio:
                pe = self.info.get('trailingPE', None)
                growth_rate = self.info.get('earningsQuarterlyGrowth', None)
                
                if pe and growth_rate:
                    growth_rate_pct = growth_rate * 100
                    if growth_rate_pct > 0:
                        peg_ratio = pe / growth_rate_pct
            
            if peg_ratio:
                return {
                    'peg_ratio': peg_ratio,
                    'undervalued': peg_ratio < 1.0,
                    'meets_criteria': peg_ratio < 1.0
                }
        except Exception:
            pass
        
        return {'peg_ratio': None, 'meets_criteria': False}
    
    # ============= TECHNICAL ANALYSIS =============
    
    def calculate_moving_averages(self) -> Dict:
        """
        Calculate 50-day and 200-day moving averages
        Check for Golden Cross
        """
        if self.data is None or len(self.data) < 200:
            return {'meets_criteria': False}
        
        try:
            current_price = self.data['Close'].iloc[-1]
            
            # Calculate MAs
            ma_50 = self.data['Close'].rolling(window=50).mean().iloc[-1]
            ma_200 = self.data['Close'].rolling(window=200).mean().iloc[-1]
            
            # Check previous day's MAs for Golden Cross
            ma_50_prev = self.data['Close'].rolling(window=50).mean().iloc[-2] if len(self.data) > 1 else ma_50
            ma_200_prev = self.data['Close'].rolling(window=200).mean().iloc[-2] if len(self.data) > 1 else ma_200
            
            # Golden Cross: 50-day crosses above 200-day
            golden_cross = (ma_50 > ma_200) and (ma_50_prev <= ma_200_prev)
            
            above_50 = current_price > ma_50
            above_200 = current_price > ma_200
            
            return {
                'current_price': current_price,
                'ma_50': ma_50,
                'ma_200': ma_200,
                'above_50': above_50,
                'above_200': above_200,
                'golden_cross': golden_cross,
                'distance_from_50': ((current_price - ma_50) / ma_50) * 100,
                'distance_from_200': ((current_price - ma_200) / ma_200) * 100,
                'meets_criteria': above_50 and above_200
            }
        except Exception:
            return {'meets_criteria': False}
    
    def calculate_relative_strength(self) -> Dict:
        """
        Calculate RS Rating (performance vs S&P 500)
        Target: RS > 80 (outperforming 80% of market)
        """
        try:
            # Get S&P 500 data for comparison
            spy = yf.Ticker('SPY')
            spy_data = spy.history(period='1y')
            
            if spy_data.empty or self.data is None:
                return {'rs_rating': None, 'meets_criteria': False}
            
            # Calculate returns over different periods
            periods = [252, 126, 63, 21]  # 1yr, 6mo, 3mo, 1mo in trading days
            stock_returns = []
            spy_returns = []
            
            for period in periods:
                if len(self.data) >= period and len(spy_data) >= period:
                    stock_ret = ((self.data['Close'].iloc[-1] - self.data['Close'].iloc[-period]) / 
                                self.data['Close'].iloc[-period]) * 100
                    spy_ret = ((spy_data['Close'].iloc[-1] - spy_data['Close'].iloc[-period]) / 
                              spy_data['Close'].iloc[-period]) * 100
                    stock_returns.append(stock_ret)
                    spy_returns.append(spy_ret)
            
            if stock_returns and spy_returns:
                # Weighted average (more weight to recent performance)
                weights = [0.4, 0.3, 0.2, 0.1]
                weighted_stock = sum(s * w for s, w in zip(stock_returns, weights))
                weighted_spy = sum(s * w for s, w in zip(spy_returns, weights))
                
                # Simple RS rating (relative outperformance)
                outperformance = weighted_stock - weighted_spy
                
                # Convert to 0-100 scale (simplified)
                # If stock outperforms by 20%+, it's in top tier
                rs_rating = min(100, max(0, 50 + outperformance))
                
                return {
                    'rs_rating': rs_rating,
                    'outperformance': outperformance,
                    'stock_return': weighted_stock,
                    'spy_return': weighted_spy,
                    'meets_criteria': rs_rating >= 80
                }
        except Exception:
            pass
        
        return {'rs_rating': None, 'meets_criteria': False}
    
    def check_volume_breakout(self) -> Dict:
        """
        Check if recent volume is 40-50% above average (breakout signal)
        """
        if self.data is None or len(self.data) < 50:
            return {'meets_criteria': False}
        
        try:
            avg_volume = self.data['Volume'].rolling(window=50).mean().iloc[-1]
            recent_volume = self.data['Volume'].iloc[-1]
            
            volume_increase_pct = ((recent_volume - avg_volume) / avg_volume) * 100
            
            return {
                'current_volume': recent_volume,
                'avg_volume': avg_volume,
                'volume_increase_pct': volume_increase_pct,
                'breakout': volume_increase_pct >= 40,
                'meets_criteria': volume_increase_pct >= 40
            }
        except Exception:
            return {'meets_criteria': False}
    
    def check_market_trend(self) -> Dict:
        """
        Check if general market (S&P 500) is in uptrend
        """
        try:
            spy = yf.Ticker('SPY')
            spy_data = spy.history(period='6mo')
            
            if spy_data.empty:
                return {'uptrend': None, 'meets_criteria': False}
            
            # Calculate SPY moving averages
            spy_ma_50 = spy_data['Close'].rolling(window=50).mean().iloc[-1]
            spy_ma_200 = spy_data['Close'].rolling(window=200).mean().iloc[-1] if len(spy_data) >= 200 else None
            spy_price = spy_data['Close'].iloc[-1]
            
            if spy_ma_200:
                uptrend = spy_price > spy_ma_50 and spy_price > spy_ma_200 and spy_ma_50 > spy_ma_200
            else:
                uptrend = spy_price > spy_ma_50
            
            return {
                'spy_price': spy_price,
                'spy_ma_50': spy_ma_50,
                'spy_ma_200': spy_ma_200,
                'uptrend': uptrend,
                'meets_criteria': uptrend
            }
        except Exception:
            return {'uptrend': None, 'meets_criteria': False}
    
    # ============= DECISION ENGINE =============
    
    def generate_signal(self) -> Dict:
        """
        Generate BUY/HOLD/SELL signal based on comprehensive analysis
        """
        if not self.fetch_data():
            return {'signal': 'ERROR', 'confidence': 0, 'reason': 'Failed to fetch data'}
        
        # Run all checks
        eps_check = self.check_eps_growth()
        annual_growth = self.check_annual_growth()
        pe_check = self.check_pe_ratio()
        peg_check = self.check_peg_ratio()
        ma_check = self.calculate_moving_averages()
        rs_check = self.calculate_relative_strength()
        volume_check = self.check_volume_breakout()
        market_check = self.check_market_trend()
        
        # BUY CRITERIA (must meet all)
        buy_criteria = {
            'fundamental': (eps_check.get('meets_criteria', False) or 
                          annual_growth.get('meets_criteria', False)),
            'technical': ma_check.get('meets_criteria', False),
            'volume': volume_check.get('meets_criteria', False),
            'market': market_check.get('meets_criteria', False)
        }
        
        buy_score = sum(buy_criteria.values())
        
        # SELL CRITERIA
        current_price = ma_check.get('current_price', 0)
        ma_50 = ma_check.get('ma_50', 0)
        ma_200 = ma_check.get('ma_200', 0)
        
        sell_reasons = []
        
        # Check if price broke below MAs on high volume
        if current_price and ma_50 and current_price < ma_50:
            sell_reasons.append("Price below 50-day MA")
        if current_price and ma_200 and current_price < ma_200:
            sell_reasons.append("Price below 200-day MA")
        
        # HOLD CRITERIA
        hold_criteria = {
            'above_50ma': ma_check.get('above_50', False),
            'positive_fundamentals': (eps_check.get('yoy_growth', -100) > 0 or 
                                     annual_growth.get('avg_growth', -100) > 0)
        }
        
        # DECISION LOGIC
        if sell_reasons:
            signal = 'SELL'
            confidence = len(sell_reasons) * 30
            reason = '; '.join(sell_reasons)
        elif buy_score == 4:
            signal = 'STRONG BUY'
            confidence = 95
            reason = 'All buy criteria met: Fundamentals + Technicals + Volume + Market'
        elif buy_score == 3:
            signal = 'BUY'
            confidence = 75
            reason = f"3 of 4 buy criteria met"
        elif sum(hold_criteria.values()) >= 1:
            signal = 'HOLD'
            confidence = 50
            reason = 'Stock maintaining support, fundamentals stable'
        else:
            signal = 'HOLD'
            confidence = 30
            reason = 'Insufficient buy/sell signals'
        
        return {
            'signal': signal,
            'confidence': min(100, confidence),
            'reason': reason,
            'analysis': {
                'eps_growth': eps_check,
                'annual_growth': annual_growth,
                'pe_ratio': pe_check,
                'peg_ratio': peg_check,
                'moving_averages': ma_check,
                'relative_strength': rs_check,
                'volume': volume_check,
                'market_trend': market_check
            },
            'buy_criteria_met': buy_criteria,
            'buy_score': f"{buy_score}/4"
        }

def analyze_stock(symbol: str) -> Dict:
    """Convenience function to analyze a stock"""
    analyzer = StockAnalyzer(symbol)
    return analyzer.generate_signal()
