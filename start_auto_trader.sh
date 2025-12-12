#!/bin/bash

# Auto-Trader Startup Script
# Runs continuous auto-trading every 5 minutes

echo "🤖 Starting Auto-Trader..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if user_id is provided
if [ -z "$1" ]; then
    echo "❌ Error: User ID required"
    echo ""
    echo "Usage: ./start_auto_trader.sh <user_id> [interval_minutes]"
    echo ""
    echo "Examples:"
    echo "  ./start_auto_trader.sh 1        # Check every 5 minutes (default)"
    echo "  ./start_auto_trader.sh 1 10     # Check every 10 minutes"
    echo ""
    exit 1
fi

USER_ID=$1
INTERVAL=${2:-5}  # Default 5 minutes

echo "User ID: $USER_ID"
echo "Check Interval: $INTERVAL minutes"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ Auto-trader is now running..."
echo "⏱️  Will check stocks every $INTERVAL minutes"
echo "🛑 Press Ctrl+C to stop"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run the auto-trader
python3 auto_trader.py $USER_ID $INTERVAL
