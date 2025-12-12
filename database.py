"""
Database module for Stock Trading SaaS Application
Handles user authentication, watchlists, trades, and settings
"""
import sqlite3
import hashlib
import secrets
from datetime import datetime
from typing import Optional, List, Dict, Tuple
import pandas as pd


class DatabaseManager:
    """Manages all database operations for the trading platform"""
    
    def __init__(self, db_path: str = "trading_platform.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Create a new database connection"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                alpaca_api_key TEXT,
                alpaca_api_secret TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # Watchlists table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlists (
                watchlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                auto_trade_enabled INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                UNIQUE(user_id, symbol)
            )
        """)
        
        # Trading sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trading_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        # Trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_id INTEGER,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                order_id TEXT,
                status TEXT DEFAULT 'pending',
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (session_id) REFERENCES trading_sessions (session_id)
            )
        """)
        
        # Stock analysis cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_cache (
                cache_id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                analysis_data TEXT NOT NULL,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol)
            )
        """)
        
        # User settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                setting_key TEXT NOT NULL,
                setting_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                UNIQUE(user_id, setting_key)
            )
        """)
        
        conn.commit()
        conn.close()
    
    # ==================== USER MANAGEMENT ====================
    
    def hash_password(self, password: str, salt: str = None) -> Tuple[str, str]:
        """Hash password with salt"""
        if salt is None:
            salt = secrets.token_hex(32)
        
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()
        
        return password_hash, salt
    
    def create_user(self, username: str, email: str, password: str) -> bool:
        """Create a new user"""
        try:
            password_hash, salt = self.hash_password(password)
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, salt)
                VALUES (?, ?, ?, ?)
            """, (username, email, password_hash, salt))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user and return user data"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT user_id, username, email, password_hash, salt, 
                   alpaca_api_key, alpaca_api_secret, is_active
            FROM users
            WHERE username = ? AND is_active = 1
        """, (username,))
        
        user = cursor.fetchone()
        
        if user:
            password_hash, _ = self.hash_password(password, user['salt'])
            
            if password_hash == user['password_hash']:
                # Update last login
                cursor.execute("""
                    UPDATE users SET last_login = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (user['user_id'],))
                conn.commit()
                
                conn.close()
                return dict(user)
        
        conn.close()
        return None
    
    def update_user_api_keys(self, user_id: int, api_key: str, api_secret: str) -> bool:
        """Update user's Alpaca API keys"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE users
                SET alpaca_api_key = ?, alpaca_api_secret = ?
                WHERE user_id = ?
            """, (api_key, api_secret, user_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating API keys: {e}")
            return False
    
    def get_user_api_keys(self, user_id: int) -> Tuple[str, str]:
        """Get user's Alpaca API keys"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT alpaca_api_key, alpaca_api_secret
            FROM users
            WHERE user_id = ?
        """, (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result['alpaca_api_key'] or '', result['alpaca_api_secret'] or ''
        return '', ''
    
    # ==================== WATCHLIST MANAGEMENT ====================
    
    def add_to_watchlist(self, user_id: int, symbol: str, auto_trade: bool = False) -> bool:
        """Add stock to user's watchlist"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO watchlists (user_id, symbol, auto_trade_enabled)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, symbol) 
                DO UPDATE SET is_active = 1, auto_trade_enabled = ?
            """, (user_id, symbol.upper(), int(auto_trade), int(auto_trade)))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error adding to watchlist: {e}")
            return False
    
    def remove_from_watchlist(self, user_id: int, symbol: str) -> bool:
        """Remove stock from watchlist"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE watchlists
                SET is_active = 0
                WHERE user_id = ? AND symbol = ?
            """, (user_id, symbol.upper()))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error removing from watchlist: {e}")
            return False
    
    def get_user_watchlist(self, user_id: int) -> List[Dict]:
        """Get user's active watchlist"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT watchlist_id, symbol, added_at, auto_trade_enabled
            FROM watchlists
            WHERE user_id = ? AND is_active = 1
            ORDER BY added_at DESC
        """, (user_id,))
        
        watchlist = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return watchlist
    
    def toggle_auto_trade(self, user_id: int, symbol: str, enabled: bool) -> bool:
        """Toggle auto-trade for a symbol"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE watchlists
                SET auto_trade_enabled = ?
                WHERE user_id = ? AND symbol = ?
            """, (int(enabled), user_id, symbol.upper()))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error toggling auto-trade: {e}")
            return False
    
    # ==================== TRADING SESSION MANAGEMENT ====================
    
    def start_trading_session(self, user_id: int) -> int:
        """Start a new trading session"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO trading_sessions (user_id)
            VALUES (?)
        """, (user_id,))
        
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return session_id
    
    def end_trading_session(self, session_id: int):
        """End a trading session"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE trading_sessions
            SET ended_at = CURRENT_TIMESTAMP, is_active = 0
            WHERE session_id = ?
        """, (session_id,))
        
        conn.commit()
        conn.close()
    
    def get_active_session(self, user_id: int) -> Optional[int]:
        """Get active trading session ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT session_id
            FROM trading_sessions
            WHERE user_id = ? AND is_active = 1
            ORDER BY started_at DESC
            LIMIT 1
        """, (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result['session_id'] if result else None
    
    # ==================== TRADE MANAGEMENT ====================
    
    def log_trade(self, user_id: int, symbol: str, action: str, side: str, 
                  quantity: int, price: float, order_id: str = None, 
                  notes: str = None) -> int:
        """Log a trade"""
        session_id = self.get_active_session(user_id)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO trades (user_id, session_id, symbol, action, side, 
                               quantity, price, order_id, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'executed', ?)
        """, (user_id, session_id, symbol.upper(), action, side, 
              quantity, price, order_id, notes))
        
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return trade_id
    
    def get_user_trades(self, user_id: int, limit: int = 100) -> pd.DataFrame:
        """Get user's trade history"""
        conn = self.get_connection()
        
        query = """
            SELECT trade_id, symbol, action, side, quantity, price, 
                   order_id, status, executed_at, notes
            FROM trades
            WHERE user_id = ?
            ORDER BY executed_at DESC
            LIMIT ?
        """
        
        df = pd.read_sql_query(query, conn, params=(user_id, limit))
        conn.close()
        return df
    
    def get_trades_by_symbol(self, user_id: int, symbol: str) -> pd.DataFrame:
        """Get trades for a specific symbol"""
        conn = self.get_connection()
        
        query = """
            SELECT trade_id, symbol, action, side, quantity, price, 
                   order_id, status, executed_at, notes
            FROM trades
            WHERE user_id = ? AND symbol = ?
            ORDER BY executed_at DESC
        """
        
        df = pd.read_sql_query(query, conn, params=(user_id, symbol.upper()))
        conn.close()
        return df
    
    # ==================== SETTINGS MANAGEMENT ====================
    
    def save_setting(self, user_id: int, key: str, value: str) -> bool:
        """Save user setting"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO user_settings (user_id, setting_key, setting_value)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, setting_key)
                DO UPDATE SET setting_value = ?, updated_at = CURRENT_TIMESTAMP
            """, (user_id, key, value, value))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving setting: {e}")
            return False
    
    def get_setting(self, user_id: int, key: str, default: str = None) -> str:
        """Get user setting"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT setting_value
            FROM user_settings
            WHERE user_id = ? AND setting_key = ?
        """, (user_id, key))
        
        result = cursor.fetchone()
        conn.close()
        
        return result['setting_value'] if result else default
    
    def get_all_settings(self, user_id: int) -> Dict[str, str]:
        """Get all user settings"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT setting_key, setting_value
            FROM user_settings
            WHERE user_id = ?
        """, (user_id,))
        
        settings = {row['setting_key']: row['setting_value'] for row in cursor.fetchall()}
        conn.close()
        return settings
