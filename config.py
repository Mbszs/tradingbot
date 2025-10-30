"""
Configuration file for XAU/USD Trading Bot
Combines ICT concepts with quantitative analysis
"""

class TradingConfig:
    """Core trading configuration"""
    
    # ========== TRADING PAIR ==========
    SYMBOL = "XAU/USD"
    
    # ========== TIMEFRAMES ==========
    TIMEFRAME_ENTRY = "1h"          # Entry timeframe
    TIMEFRAME_STRUCTURE = "4h"       # Structure/trend timeframe
    TIMEFRAME_HTF = "1d"             # Higher timeframe for bias
    
    # ========== TREND DETECTION ==========
    EMA_FAST = 50                    # Fast EMA for trend
    EMA_SLOW = 200                   # Slow EMA for trend
    EMA_20 = 20                      # Short-term EMA for ribbon
    
    # ========== QUANTITATIVE INDICATORS ==========
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    RSI_PERIOD = 14
    RSI_LONG_THRESHOLD = 50          # RSI must be > 50 for longs
    RSI_SHORT_THRESHOLD = 50         # RSI must be < 50 for shorts
    ATR_PERIOD = 14
    ATR_MIN_THRESHOLD = 0.5          # Minimum ATR to trade (avoid low volatility)
    
    # ========== ICT CONCEPTS ==========
    FVG_MIN_SIZE = 0.3               # Minimum FVG size in ATR multiples
    OB_LOOKBACK = 50                 # Candles to look back for order blocks
    OB_MIN_BODY_PERCENT = 0.6        # Min body % for strong order block
    LIQUIDITY_LOOKBACK = 20          # Candles for liquidity pool detection
    
    # ========== MARKET STRUCTURE ==========
    SWING_LOOKBACK = 10              # Candles for swing high/low detection
    STRUCTURE_BREAK_CONFIRMATION = 1 # Candles to confirm structure break
    
    # ========== ENTRY FILTERS ==========
    MAX_DISTANCE_FROM_MA = 2.0       # Max ATR distance from 50 EMA to enter
    MIN_VOLUME_SPIKE = 1.2           # Min volume spike (1.2x average)
    MACD_HISTOGRAM_EXPANSION = True  # Require MACD histogram expansion
    
    # ========== RISK MANAGEMENT ==========
    RISK_PER_TRADE = 0.01            # 1% risk per trade
    MAX_RISK_PER_TRADE = 0.02        # 2% absolute max
    STOP_LOSS_ATR = 1.5              # Stop loss in ATR multiples
    
    # Partial profit taking
    TAKE_PROFIT_1 = 1.5              # First TP at 1.5R
    TAKE_PROFIT_1_SIZE = 0.33        # Close 33% at TP1
    TAKE_PROFIT_2 = 2.5              # Second TP at 2.5R
    TAKE_PROFIT_2_SIZE = 0.33        # Close 33% at TP2
    TRAILING_STOP_ACTIVATION = 2.0   # Activate trailing stop at 2R
    TRAILING_STOP_ATR = 1.0          # Trail with 1 ATR
    
    # ========== POSITION SIZING ==========
    DYNAMIC_SIZING = True            # Use ATR-based position sizing
    BASE_POSITION_SIZE = 0.01        # Base position size (1 mini lot = 0.01)
    MAX_POSITION_SIZE = 0.10         # Maximum position size
    
    # ========== SAFETY MECHANISMS ==========
    MAX_CONSECUTIVE_LOSSES = 3       # Stop after 3 consecutive losses
    COOLDOWN_PERIOD = 4              # Hours to wait after max losses
    MAX_DAILY_LOSS = 0.03            # 3% max daily loss
    MAX_OPEN_TRADES = 2              # Maximum concurrent trades
    
    # ========== SESSION FILTERS ==========
    ENABLE_SESSION_FILTER = True
    AVOID_ASIAN_SESSION = True       # Avoid low liquidity Asian session
    # Trading hours in UTC
    LONDON_OPEN = 8                  # 08:00 UTC
    LONDON_CLOSE = 16                # 16:00 UTC
    NY_OPEN = 13                     # 13:00 UTC
    NY_CLOSE = 21                    # 21:00 UTC
    
    # ========== BACKTESTING ==========
    BACKTEST_START = "2022-01-01"
    BACKTEST_END = "2024-12-31"
    INITIAL_CAPITAL = 10000          # Starting capital
    COMMISSION = 0.0001              # Commission per trade (1 pip)
    SLIPPAGE = 0.5                   # Slippage in pips
    
    # ========== DATA & LOGGING ==========
    DATA_PATH = "data/"
    LOG_PATH = "logs/"
    RESULTS_PATH = "results/"
    ENABLE_LOGGING = True
    LOG_LEVEL = "INFO"


class ICTConfig:
    """ICT-specific configuration"""
    
    # Fair Value Gaps
    FVG_TYPES = ["bullish", "bearish"]
    FVG_FILL_THRESHOLD = 0.5         # 50% fill to consider FVG mitigated
    
    # Order Blocks
    OB_VALIDATION_TOUCHES = 0        # Min touches to validate OB (0 = fresh)
    OB_MAX_AGE = 100                 # Max candles for OB to remain valid
    
    # Liquidity
    LIQUIDITY_TYPES = ["buy_side", "sell_side", "equal_highs", "equal_lows"]
    EQUAL_LEVEL_TOLERANCE = 0.0002   # 2 pips tolerance for equal highs/lows
    
    # Kill Zones (ICT high-probability times)
    ASIAN_KILL_ZONE = (0, 4)         # 00:00-04:00 UTC
    LONDON_KILL_ZONE = (8, 10)       # 08:00-10:00 UTC
    NY_KILL_ZONE = (13, 15)          # 13:00-15:00 UTC
    LONDON_CLOSE_KILL_ZONE = (15, 17) # 15:00-17:00 UTC
