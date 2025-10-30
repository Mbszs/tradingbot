"""
Configuration file for ICT XAUUSD Automated Trading System
"""

# ============================================================================
# BROKER & SYMBOL CONFIGURATION
# ============================================================================
SYMBOL = "XAUUSD"
TIMEFRAMES = {
    'DAILY': '1D',
    'H4': '4H',
    'H1': '1H',
    'M15': '15m',
    'M5': '5m',
    'M1': '1m'
}

# ============================================================================
# SESSION TIMING (GMT)
# ============================================================================
SESSIONS = {
    'ASIA': {
        'start': '23:00',
        'end': '06:00',
        'enabled': True
    },
    'LONDON': {
        'start': '07:00',
        'end': '11:00',
        'enabled': True
    },
    'NEWYORK': {
        'start': '12:00',
        'end': '20:00',
        'enabled': False  # No trading during NY session
    }
}

# ============================================================================
# RISK MANAGEMENT
# ============================================================================
RISK_CONFIG = {
    'risk_per_trade_pct': 1.0,          # 1% risk per trade
    'max_daily_drawdown_pct': 3.0,      # 3% max daily drawdown
    'max_trades_per_session': 2,        # Max 2 trades per session
    'max_open_positions': 1,            # Only 1 position at a time
    'account_balance': 10000,           # Starting balance (adjust as needed)
    'partial_tp_pct': 50,               # Take 50% at 1R
    'breakeven_trigger_r': 1.0,         # Move to BE after 1R
    'min_rr_ratio': 2.0                 # Minimum Risk:Reward ratio
}

# ============================================================================
# ICT CONCEPTS CONFIGURATION
# ============================================================================
ICT_CONFIG = {
    # Market Structure
    'structure_lookback': 50,           # Bars to look back for structure
    'structure_min_move_pct': 0.1,      # Min % move to confirm MSS/CHOCH
    
    # Liquidity
    'liquidity_lookback': 100,          # Bars to identify equal highs/lows
    'liquidity_tolerance_pips': 2,      # Tolerance for "equal" levels
    'liquidity_sweep_pips': 3,          # Pips beyond level to confirm sweep
    
    # Order Blocks
    'ob_lookback': 50,                  # Bars to look for OBs
    'ob_min_displacement_pct': 0.15,    # Min % displacement to validate OB
    'ob_body_size_min_pct': 30,         # OB candle body must be >30% of range
    
    # Fair Value Gaps
    'fvg_min_gap_pips': 5,              # Minimum gap size in pips
    'fvg_lookback': 50,                 # Bars to look for FVGs
    
    # Fibonacci OTE
    'fib_ote_min': 0.618,               # OTE zone minimum
    'fib_ote_max': 0.79,                # OTE zone maximum
    'fib_lookback': 20                  # Bars for swing high/low
}

# ============================================================================
# QUANTITATIVE FILTERS
# ============================================================================
QUANT_FILTERS = {
    # Volatility Filter (ATR)
    'atr_period': 14,
    'atr_min_multiplier': 0.8,          # Skip if ATR < 0.8 × average
    'atr_max_multiplier': 2.0,          # Skip if ATR > 2.0 × average (news)
    'atr_lookback': 100,                # Periods for average ATR
    
    # Volume Filter
    'volume_period': 20,                # Rolling mean period
    'volume_min_multiplier': 1.0,       # Volume must be > 1.0 × mean
    
    # Correlation Filter
    'correlation_enabled': True,
    'correlation_symbols': ['DXY', 'US10Y'],
    'correlation_period': 50,
    'correlation_threshold': 0.7,       # |correlation| must be > 0.7
    
    # Trend Filter
    'trend_filter_type': 'linear_regression',  # or 'kalman_filter'
    'trend_period': 20,
    'trend_strength_threshold': 0.3,    # Min slope strength
    
    # Machine Learning (optional)
    'ml_enabled': False,
    'ml_model_path': 'models/ict_classifier.pkl',
    'ml_confidence_threshold': 0.7
}

# ============================================================================
# ENTRY CONFLUENCE REQUIREMENTS
# ============================================================================
ENTRY_CONFLUENCE = {
    'required_confluences': 3,          # Minimum confluence factors needed
    'factors': {
        'liquidity_sweep': True,        # Must have liquidity sweep
        'structure_shift': True,        # Must have MSS/CHOCH
        'ob_or_fvg': True,              # Must retrace to OB or FVG
        'ote_zone': False,              # Optional: in OTE zone
        'volume_spike': True,           # Volume above threshold
        'atr_valid': True,              # ATR within valid range
        'trend_aligned': True           # Trend filter aligned
    }
}

# ============================================================================
# TECHNICAL INDICATORS
# ============================================================================
INDICATORS = {
    'atr_period': 14,
    'ema_fast': 9,
    'ema_slow': 21,
    'rsi_period': 14,
    'volume_sma': 20
}

# ============================================================================
# BROKER API CONFIGURATION (Placeholder - adjust for your broker)
# ============================================================================
BROKER_CONFIG = {
    'broker_type': 'MT5',  # or 'OANDA', 'IB', 'ALPACA', etc.
    'api_key': 'YOUR_API_KEY',
    'api_secret': 'YOUR_API_SECRET',
    'account_id': 'YOUR_ACCOUNT_ID',
    'server': 'YOUR_BROKER_SERVER',
    'live_trading': False,  # Set to True for live trading
    'paper_trading': True   # Set to False when live
}

# ============================================================================
# LOGGING & MONITORING
# ============================================================================
LOGGING_CONFIG = {
    'log_level': 'INFO',  # DEBUG, INFO, WARNING, ERROR
    'log_file': 'logs/trading_bot.log',
    'log_trades': True,
    'log_signals': True,
    'save_charts': True,
    'chart_output_dir': 'charts/'
}

# ============================================================================
# BACKTESTING
# ============================================================================
BACKTEST_CONFIG = {
    'start_date': '2023-01-01',
    'end_date': '2024-12-31',
    'initial_balance': 10000,
    'data_source': 'yahoo',  # or 'mt5', 'oanda', etc.
}
