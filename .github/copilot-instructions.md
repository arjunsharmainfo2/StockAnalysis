# Copilot / AI Agent Instructions

**Purpose:** Give AI coding agents immediate, practical context for working in this repository so they can make safe, focused edits.

- **Repo layout:** top-level single-file Python scripts. Primary files: `auto_sim_bot.py` (simulator CLI), `bot_dashboard.py` (Streamlit UI). There are several backup copies named like `bot_dashboard copy.py`.
- **Runtime:** no packaging; scripts are executed directly. Typical commands:
  - `pip install pandas alpaca-trade-api streamlit`
  - `python3 auto_sim_bot.py` — runs the simulated trading loop and writes `sim_trades.csv` / `sim_equity.csv`.
  - `streamlit run bot_dashboard.py` — launches the Streamlit dashboard.

**Big picture / architecture**
- `auto_sim_bot.py`: a single `Simulator` class that
  - pulls minute bars via Alpaca (`get_bars()`),
  - computes indicators (MA, RSI, volume average),
  - decides signals in `signal()` and executes simulated entries/exits (`enter_long`, `enter_short`, `manage_exits`),
  - writes trade and equity logs to CSV files named by constants `LOG_TRADES_CSV` / `LOG_EQUITY_CSV`.
- `bot_dashboard.py`: lightweight Streamlit front-end. It uses Alpaca bars and a simple MA10/MA20 crossover in `process_stock()` and optionally submits real orders when the `auto_trade` checkbox is set.

**Data flow and integration points**
- Market data and order calls use the Alpaca REST client `alpaca_trade_api.REST` in both files.
- Persistent outputs are CSV logs in the repo working directory (see `LOG_TRADES_CSV`, `LOG_EQUITY_CSV`).

**Project-specific conventions & patterns**
- Single-file scripts with top-of-file constants for configuration (API keys, watchlists, indicator windows). Prefer editing constants for quick tweaks.
- Indicator helpers live in the same file (e.g., `rsi()` in `auto_sim_bot.py`). When adding indicators, use the same pandas-first style.
- Logging is file-based CSV append; keep the CSV columns consistent when changing `_log_trade()` or `flush_equity()` formats.

**Secrets & safety (important)**
- The repo currently contains hard-coded Alpaca API keys in `auto_sim_bot.py` and `bot_dashboard.py`. Do NOT expose or commit real keys.
- If you need to run code, prefer setting environment variables and switching code to read `os.getenv('APCA_API_KEY_ID')` / `APCA_API_SECRET_KEY` (there is commented example in `auto_sim_bot.py`).

**Developer workflows & debugging**
- There is no `requirements.txt` or test suite — create `requirements.txt` when adding dependencies.
- Quick local run: install dependencies, then run `python3 auto_sim_bot.py` or `streamlit run bot_dashboard.py`.
- For fast debugging of strategy logic, run the script and add short-lived `print()` statements near `signal()` and `get_bars()` or write a small unit wrapper that loads sample bars and calls `signal()`.

**When making changes, follow these rules for AI edits**
- Preserve public APIs (file names and CSV column formats) unless explicitly migrating them.
- Never add or commit secrets. If a change requires keys, modify code to use `os.getenv()` and document the env variables in the PR.
- Keep changes minimal: prefer small, well-scoped edits (e.g., add an indicator function or change a constant) rather than large refactors.
- If adding dependencies, update `requirements.txt` and mention the install command in commit/PR.

**Files to inspect for examples / entry points**
- `auto_sim_bot.py` — `Simulator.get_bars()`, `Simulator.signal()`, `enter_long()` / `exit_position()`, `mark_equity()`.
- `bot_dashboard.py` — `process_stock()` and Streamlit UI flow (checkbox, `st.rerun()`).

If any part of the environment is unclear (expected Python version, preferred dependency pinning, CI), tell me and I will add a short follow-up section. Ready to update or expand this file based on your feedback.
