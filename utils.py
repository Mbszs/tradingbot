"""
Utility Functions
Common helper functions used across the trading system
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging


def setup_logger(name: str, log_file: str = 'logs/trading.log', 
                level: int = logging.INFO) -> logging.Logger:
    """
    Setup logger with file and console handlers
    
    Args:
        name: Logger name
        log_file: Path to log file
        level: Logging level
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(level)
    fh.setFormatter(formatter)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(formatter)
    
    # Add handlers
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger


def pips_to_price(pips: float, symbol: str = 'XAUUSD') -> float:
    """
    Convert pips to price difference
    
    Args:
        pips: Number of pips
        symbol: Trading symbol
        
    Returns:
        Price difference
    """
    pip_values = {
        'XAUUSD': 0.01,  # 1 pip = $0.01
        'EURUSD': 0.0001,
        'GBPUSD': 0.0001,
        'USDJPY': 0.01
    }
    
    return pips * pip_values.get(symbol, 0.01)


def price_to_pips(price_diff: float, symbol: str = 'XAUUSD') -> float:
    """
    Convert price difference to pips
    
    Args:
        price_diff: Price difference
        symbol: Trading symbol
        
    Returns:
        Number of pips
    """
    pip_values = {
        'XAUUSD': 0.01,
        'EURUSD': 0.0001,
        'GBPUSD': 0.0001,
        'USDJPY': 0.01
    }
    
    return price_diff / pip_values.get(symbol, 0.01)


def calculate_lot_size(account_balance: float, 
                      risk_pct: float,
                      stop_loss_pips: float,
                      symbol: str = 'XAUUSD') -> float:
    """
    Calculate position size in lots
    
    Args:
        account_balance: Account balance in dollars
        risk_pct: Risk percentage (e.g., 1.0 for 1%)
        stop_loss_pips: Stop loss distance in pips
        symbol: Trading symbol
        
    Returns:
        Position size in lots
    """
    risk_amount = account_balance * (risk_pct / 100)
    
    # Pip values per standard lot
    pip_values = {
        'XAUUSD': 10.0,  # $10 per pip per lot
        'EURUSD': 10.0,
        'GBPUSD': 10.0,
        'USDJPY': 8.0
    }
    
    pip_value = pip_values.get(symbol, 10.0)
    
    if stop_loss_pips > 0:
        lot_size = risk_amount / (stop_loss_pips * pip_value)
    else:
        lot_size = 0.01
    
    return round(lot_size, 2)


def validate_dataframe(df: pd.DataFrame, required_columns: List[str] = None) -> bool:
    """
    Validate that DataFrame has required structure
    
    Args:
        df: DataFrame to validate
        required_columns: List of required column names
        
    Returns:
        True if valid, False otherwise
    """
    if df is None or df.empty:
        return False
    
    if required_columns is None:
        required_columns = ['open', 'high', 'low', 'close']
    
    return all(col in df.columns for col in required_columns)


def resample_timeframe(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    Resample DataFrame to different timeframe
    
    Args:
        df: DataFrame with OHLC data
        timeframe: Target timeframe ('5T', '15T', '1H', '4H', '1D')
        
    Returns:
        Resampled DataFrame
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be DatetimeIndex")
    
    resampled = df.resample(timeframe).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
    
    return resampled.dropna()


def format_trade_message(trade: Dict) -> str:
    """
    Format trade information for logging/notification
    
    Args:
        trade: Trade dictionary
        
    Returns:
        Formatted string
    """
    direction = trade.get('direction', 'UNKNOWN')
    entry = trade.get('entry_price', 0)
    sl = trade.get('stop_loss', 0)
    tp = trade.get('take_profit', 0)
    size = trade.get('position_size', 0)
    
    sl_pips = abs(entry - sl) / 0.01
    tp_pips = abs(tp - entry) / 0.01
    rr_ratio = tp_pips / sl_pips if sl_pips > 0 else 0
    
    message = f"""
    🎯 NEW TRADE SIGNAL
    Direction: {direction}
    Entry: {entry:.2f}
    Stop Loss: {sl:.2f} ({sl_pips:.1f} pips)
    Take Profit: {tp:.2f} ({tp_pips:.1f} pips)
    R:R Ratio: 1:{rr_ratio:.1f}
    Position Size: {size:.2f} lots
    """
    
    return message.strip()


def calculate_drawdown(equity_curve: List[float]) -> Tuple[float, float]:
    """
    Calculate maximum drawdown from equity curve
    
    Args:
        equity_curve: List of equity values
        
    Returns:
        Tuple of (max_drawdown_pct, max_drawdown_amount)
    """
    if not equity_curve or len(equity_curve) < 2:
        return 0.0, 0.0
    
    equity_array = np.array(equity_curve)
    running_max = np.maximum.accumulate(equity_array)
    drawdown = (equity_array - running_max) / running_max * 100
    
    max_dd_pct = np.min(drawdown)
    max_dd_idx = np.argmin(drawdown)
    max_dd_amount = equity_array[max_dd_idx] - running_max[max_dd_idx]
    
    return abs(max_dd_pct), abs(max_dd_amount)


def calculate_sharpe_ratio(returns: List[float], 
                          risk_free_rate: float = 0.02) -> float:
    """
    Calculate Sharpe ratio
    
    Args:
        returns: List of period returns
        risk_free_rate: Annual risk-free rate
        
    Returns:
        Sharpe ratio
    """
    if not returns or len(returns) < 2:
        return 0.0
    
    returns_array = np.array(returns)
    excess_returns = returns_array - (risk_free_rate / 252)  # Daily risk-free rate
    
    if np.std(excess_returns) == 0:
        return 0.0
    
    sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
    return sharpe


def is_market_open(timestamp: pd.Timestamp) -> bool:
    """
    Check if forex market is open (24/5)
    
    Args:
        timestamp: Timestamp to check
        
    Returns:
        True if market is open
    """
    # Forex market closed on weekends
    if timestamp.weekday() >= 5:  # Saturday or Sunday
        return False
    
    # Check for Friday close (22:00 GMT) and Sunday open (22:00 GMT)
    if timestamp.weekday() == 4:  # Friday
        if timestamp.hour >= 22:
            return False
    
    return True


def calculate_position_value(position_size: float, 
                            price: float,
                            symbol: str = 'XAUUSD') -> float:
    """
    Calculate position value in dollars
    
    Args:
        position_size: Position size in lots
        price: Current price
        symbol: Trading symbol
        
    Returns:
        Position value in dollars
    """
    if symbol == 'XAUUSD':
        # 1 lot = 100 oz of gold
        return position_size * 100 * price
    
    elif symbol in ['EURUSD', 'GBPUSD']:
        # 1 lot = 100,000 units
        return position_size * 100000
    
    else:
        return position_size * 100000  # Default to standard lot


def time_to_next_session(current_time: datetime, 
                         sessions: Dict) -> timedelta:
    """
    Calculate time until next trading session
    
    Args:
        current_time: Current datetime
        sessions: Dictionary of session configurations
        
    Returns:
        Timedelta to next session
    """
    # This is a simplified version
    # Full implementation would check all sessions and find closest one
    
    current_hour = current_time.hour
    
    # Asia session starts at 23:00
    if current_hour < 23:
        hours_until = 23 - current_hour
        return timedelta(hours=hours_until)
    
    # London session starts at 07:00
    if current_hour < 7:
        hours_until = 7 - current_hour
        return timedelta(hours=hours_until)
    
    # Next session is tomorrow at 23:00
    hours_until = 24 - current_hour + 23
    return timedelta(hours=hours_until)


def format_performance_report(stats: Dict) -> str:
    """
    Format performance statistics into readable report
    
    Args:
        stats: Dictionary with trading statistics
        
    Returns:
        Formatted report string
    """
    report = f"""
    ═══════════════════════════════════════════════════════════════
                        TRADING PERFORMANCE REPORT
    ═══════════════════════════════════════════════════════════════
    
    TRADE STATISTICS:
    ─────────────────────────────────────────────────────────────
    Total Trades:           {stats.get('total_trades', 0)}
    Winning Trades:         {stats.get('winning_trades', 0)}
    Losing Trades:          {stats.get('losing_trades', 0)}
    Win Rate:              {stats.get('win_rate', 0):.2f}%
    
    PROFITABILITY:
    ─────────────────────────────────────────────────────────────
    Total P&L:             ${stats.get('total_pnl', 0):.2f}
    Total P&L %:           {stats.get('total_pnl_pct', 0):.2f}%
    Average Win:           ${stats.get('avg_win', 0):.2f}
    Average Loss:          ${stats.get('avg_loss', 0):.2f}
    Largest Win:           ${stats.get('largest_win', 0):.2f}
    Largest Loss:          ${stats.get('largest_loss', 0):.2f}
    Profit Factor:         {stats.get('profit_factor', 0):.2f}
    
    RISK METRICS:
    ─────────────────────────────────────────────────────────────
    Max Drawdown:          {stats.get('max_drawdown', 0):.2f}%
    Sharpe Ratio:          {stats.get('sharpe_ratio', 0):.2f}
    
    ═══════════════════════════════════════════════════════════════
    """
    
    return report.strip()


def save_trade_to_csv(trade: Dict, filename: str = 'trades.csv'):
    """
    Save trade to CSV file for record keeping
    
    Args:
        trade: Trade dictionary
        filename: CSV filename
    """
    import os
    
    # Create DataFrame with trade data
    trade_df = pd.DataFrame([trade])
    
    # Append to CSV
    if os.path.exists(filename):
        trade_df.to_csv(filename, mode='a', header=False, index=False)
    else:
        trade_df.to_csv(filename, mode='w', header=True, index=False)
