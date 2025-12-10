#!/usr/bin/env python3
"""
Quick test script to verify Alpaca API credentials and data fetching.
Run this to debug connection issues.
"""
import os
from alpaca_trade_api.rest import REST, TimeFrame
import yfinance as yf

print("="*60)
print("ALPACA & YAHOO FINANCE API TEST")
print("="*60)

# Test 1: Check environment variables
print("\n1. Checking environment variables...")
API_KEY = os.getenv("APCA_API_KEY_ID", "")
API_SECRET = os.getenv("APCA_API_SECRET_KEY", "")
BASE_URL = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")

if API_KEY:
    print(f"   ✅ APCA_API_KEY_ID found: {API_KEY[:8]}...")
else:
    print("   ❌ APCA_API_KEY_ID not set!")
    
if API_SECRET:
    print(f"   ✅ APCA_API_SECRET_KEY found: {API_SECRET[:8]}...")
else:
    print("   ❌ APCA_API_SECRET_KEY not set!")

print(f"   📍 BASE_URL: {BASE_URL}")

# Test 2: Initialize Alpaca API
print("\n2. Initializing Alpaca API...")
if not API_KEY or not API_SECRET:
    print("   ❌ Cannot initialize API - credentials missing")
    print("\n   💡 Set credentials using:")
    print("      export APCA_API_KEY_ID='your_key_here'")
    print("      export APCA_API_SECRET_KEY='your_secret_here'")
    api = None
else:
    try:
        api = REST(API_KEY, API_SECRET, BASE_URL)
        print("   ✅ Alpaca API initialized")
    except Exception as e:
        print(f"   ❌ Failed to initialize API: {e}")
        api = None

# Test 3: Fetch account info
if api:
    print("\n3. Fetching account info...")
    try:
        account = api.get_account()
        print(f"   ✅ Account Status: {account.status}")
        print(f"   💰 Buying Power: ${float(account.buying_power):,.2f}")
        print(f"   📊 Equity: ${float(account.equity):,.2f}")
    except Exception as e:
        print(f"   ❌ Failed to fetch account: {e}")

# Test 4: Fetch bar data
if api:
    print("\n4. Fetching bar data for AAPL...")
    try:
        bars = api.get_bars("AAPL", TimeFrame.Day, limit=5).df
        if bars.empty:
            print("   ❌ No data returned")
        else:
            print(f"   ✅ Fetched {len(bars)} bars")
            print(f"   Latest close: ${bars['close'].iloc[-1]:.2f}")
            print("\n   Sample data:")
            print(bars[['close', 'volume']].tail(3))
    except Exception as e:
        print(f"   ❌ Failed to fetch bars: {e}")

# Test 5: Yahoo Finance
print("\n5. Testing Yahoo Finance for AAPL...")
try:
    ticker = yf.Ticker("AAPL")
    info = ticker.info
    print(f"   ✅ Current Price: ${info.get('currentPrice', 'N/A')}")
    print(f"   📈 Market Cap: ${info.get('marketCap', 0):,.0f}")
    print(f"   📊 PE Ratio: {info.get('trailingPE', 'N/A')}")
    
    # Test news
    news = getattr(ticker, "news", [])
    print(f"   📰 News items available: {len(news)}")
    if news:
        print(f"   Latest headline: {news[0].get('title', 'N/A')[:60]}...")
except Exception as e:
    print(f"   ❌ Yahoo Finance error: {e}")

print("\n" + "="*60)
print("TEST COMPLETE")
print("="*60)
