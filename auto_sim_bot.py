#!/usr/bin/env python3
import os
import time
from dataclasses import dataclass
from typing import Dict, Optional, List

import pandas as pd
from alpaca_trade_api.rest import REST, TimeFrame

# ========= USER SETTINGS =========
API_KEY = os.getenv("APCA_API_KEY_ID", "")
API_SECRET = os.getenv("APCA_API_SECRET_KEY", "")
BASE_URL = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets/")

WATCHLIST   = ["AAPL", "MSFT", "AMZN", "GOOGL", "TSLA"]   # tweak as you like
BAR_LIMIT   = 300                                         # number of minute bars to pull
INTERVAL_S  = 60                                          # loop interval in seconds
QTY         = 1                                           # simulated position size (shares)
SL_PCT      = 0.02                                        # stop-loss %
TP_PCT      = 0.05                                        # take-profit %
VOL_WIN     = 20                                          # volume avg window
MA_SHORT    = 5
MA_LONG     = 20
RSI_WIN     = 14

LOG_TRADES_CSV = "sim_trades.csv"
LOG_EQUITY_CSV = "sim_equity.csv"
# =================================


# ---------- Helpers ----------
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Pandas RSI (no TA-Lib)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


@dataclass
class Position:
    side: str           # "LONG" or "SHORT"
    qty: int
    entry: float
    stop: float
    take: float

    def unrealized(self, price: float) -> float:
        if self.side == "LONG":
            return (price - self.entry) * self.qty
        else:
            return (self.entry - price) * self.qty


class Simulator:
    def __init__(self):
        self.api = REST(API_KEY, API_SECRET, BASE_URL)
        self.positions: Dict[str, Position] = {}
        self.cash: float = 100000.0  # starting cash
        self.equity: float = self.cash
        self.trade_log: List[dict] = []
        self.equity_log: List[dict] = []

        # init CSVs
        if not os.path.exists(LOG_TRADES_CSV):
            pd.DataFrame(columns=[
                "timestamp","symbol","action","side","qty","price","cash_after","note"
            ]).to_csv(LOG_TRADES_CSV, index=False)
        if not os.path.exists(LOG_EQUITY_CSV):
            pd.DataFrame(columns=[
                "timestamp","equity","cash","positions_value"
            ]).to_csv(LOG_EQUITY_CSV, index=False)

    # ---- Data ----
    def get_bars(self, symbol: str, limit: int = BAR_LIMIT) -> pd.DataFrame:
        df = self.api.get_bars(symbol, TimeFrame.Minute, limit=limit).df
        if df.empty:
            return df
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        # Indicators
        df["MA_S"] = df["close"].rolling(MA_SHORT).mean()
        df["MA_L"] = df["close"].rolling(MA_LONG).mean()
        df["RSI"]  = rsi(df["close"], RSI_WIN)
        df["VOLAVG"] = df["volume"].rolling(VOL_WIN).mean()
        return df

    # ---- Signals ----
    def signal(self, df: pd.DataFrame) -> str:
        if df.empty:
            return "HOLD"
        latest = df.iloc[-1]
        # guard against NaNs
        needed = ["MA_S","MA_L","RSI","volume","VOLAVG","close"]
        if any(pd.isna(latest[k]) for k in needed):
            return "HOLD"

        bullish = (latest["MA_S"] > latest["MA_L"]) and (latest["RSI"] < 70) and (latest["volume"] > latest["VOLAVG"])
        bearish = (latest["MA_S"] < latest["MA_L"]) and (latest["RSI"] > 30) and (latest["volume"] > latest["VOLAVG"])

        if bullish:
            return "BUY"
        if bearish:
            return "SELL"
        return "HOLD"

    # ---- Sim Execution ----
    def enter_long(self, symbol: str, price: float):
        if symbol in self.positions:
            return
        cost = price * QTY
        if self.cash < cost:
            self._log_trade(symbol, "REJECT", "LONG", 0, price, "Insufficient cash")
            return
        self.cash -= cost
        pos = Position(
            side="LONG",
            qty=QTY,
            entry=price,
            stop=price * (1 - SL_PCT),
            take=price * (1 + TP_PCT),
        )
        self.positions[symbol] = pos
        self._log_trade(symbol, "OPEN", "LONG", QTY, price, "Enter long")

    def enter_short(self, symbol: str, price: float):
        if symbol in self.positions:
            return
        # For simplicity, allow short with no borrow checks; mark-to-market handled.
        pos = Position(
            side="SHORT",
            qty=QTY,
            entry=price,
            stop=price * (1 + SL_PCT),
            take=price * (1 - TP_PCT),
        )
        self.positions[symbol] = pos
        self._log_trade(symbol, "OPEN", "SHORT", QTY, price, "Enter short")

    def exit_position(self, symbol: str, price: float, note: str):
        pos = self.positions.get(symbol)
        if not pos:
            return
        # PnL & cash update
        if pos.side == "LONG":
            pnl = (price - pos.entry) * pos.qty
            self.cash += price * pos.qty
        else:  # SHORT
            pnl = (pos.entry - price) * pos.qty
            # short: realize pnl into cash; assume no margin accounting for simplicity
            self.cash += pnl
        self._log_trade(symbol, "CLOSE", pos.side, pos.qty, price, note + f" | PnL={pnl:.2f}")
        del self.positions[symbol]

    def manage_exits(self, symbol: str, price: float):
        pos = self.positions.get(symbol)
        if not pos:
            return
        if pos.side == "LONG":
            if price <= pos.stop:
                self.exit_position(symbol, price, "Stop-loss hit")
            elif price >= pos.take:
                self.exit_position(symbol, price, "Take-profit hit")
        else:  # SHORT
            if price >= pos.stop:
                self.exit_position(symbol, price, "Stop-loss hit")
            elif price <= pos.take:
                self.exit_position(symbol, price, "Take-profit hit")

    # ---- Accounting ----
    def mark_equity(self, prices: Dict[str, float], timestamp: pd.Timestamp):
        positions_value = 0.0
        for sym, pos in self.positions.items():
            px = prices.get(sym)
            if px is None:
                continue
            positions_value += pos.unrealized(px) + (pos.entry * pos.qty if pos.side == "LONG" else 0)
            # For short, we’re already counting unrealized pnl in unrealized() and add to cash at close; keep simple view.

        # Simplified equity = cash + sum unrealized PnL for all positions
        unrealized_total = sum(
            self.positions[s].unrealized(prices[s]) for s in self.positions.keys() if s in prices
        )
        equity_now = self.cash + unrealized_total
        self.equity = equity_now

        self.equity_log.append({
            "timestamp": pd.Timestamp(timestamp).isoformat(),
            "equity": round(equity_now, 2),
            "cash": round(self.cash, 2),
            "positions_value": round(positions_value, 2),
        })

    # ---- Logging ----
    def _log_trade(self, symbol: str, action: str, side: str, qty: int, price: float, note: str):
        row = {
            "timestamp": pd.Timestamp.utcnow().isoformat(),
            "symbol": symbol,
            "action": action,
            "side": side,
            "qty": qty,
            "price": round(price, 4),
            "cash_after": round(self.cash, 2),
            "note": note,
        }
        self.trade_log.append(row)
        pd.DataFrame([row]).to_csv(LOG_TRADES_CSV, mode="a", header=False, index=False)

    def flush_equity(self):
        if self.equity_log:
            pd.DataFrame(self.equity_log).to_csv(LOG_EQUITY_CSV, mode="a", header=False, index=False)
            self.equity_log = []

    # ---- Main loop ----
    def run(self):
        print(f"Starting SIM with cash ${self.cash:,.2f} | Watchlist: {', '.join(WATCHLIST)}")
        try:
            while True:
                prices = {}
                print("\n--- Tick ---")
                for symbol in WATCHLIST:
                    try:
                        df = self.get_bars(symbol, BAR_LIMIT)
                        if df.empty or len(df) < max(MA_LONG, RSI_WIN, VOL_WIN) + 1:
                            print(f"{symbol}: not enough data")
                            continue

                        px = float(df["close"].iloc[-1])
                        prices[symbol] = px

                        sig = self.signal(df)
                        pos = self.positions.get(symbol)
                        print(f"{symbol}: px={px:.2f} sig={sig} pos={pos.side if pos else '-'}")

                        # exits first
                        self.manage_exits(symbol, px)

                        # entries
                        if sig == "BUY" and symbol not in self.positions:
                            self.enter_long(symbol, px)
                        elif sig == "SELL" and symbol not in self.positions:
                            self.enter_short(symbol, px)
                    except Exception as e:
                        print(f"{symbol}: error -> {e}")

                # mark equity
                ts = pd.Timestamp.utcnow()
                self.mark_equity(prices, ts)
                self.flush_equity()

                print(f"Equity: ${self.equity:,.2f} | Cash: ${self.cash:,.2f} | Open: {len(self.positions)}")
                time.sleep(INTERVAL_S)
        except KeyboardInterrupt:
            print("\nStopping… writing final logs.")
            self.flush_equity()
            print(f"Final Equity: ${self.equity:,.2f} | Cash: ${self.cash:,.2f} | Open: {len(self.positions)}")


if __name__ == "__main__":
    if not API_KEY or not API_SECRET:
        print("⚠️ Set APCA_API_KEY_ID and APCA_API_SECRET_KEY env vars before running.")
    bot = Simulator()
    bot.run()