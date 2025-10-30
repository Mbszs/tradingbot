# ICT XAUUSD Automated Trading System

A fully automated trading system for XAUUSD (Gold/USD) based on **Inner Circle Trader (ICT) Smart Money Concepts** combined with quantitative filters.

## 🎯 Overview

This trading system implements:

- **ICT Core Concepts**: Market Structure, MSS/CHOCH, Liquidity Sweeps, Order Blocks, Fair Value Gaps, Fibonacci OTE
- **Session-Based Trading**: Asia (23:00-06:00 GMT) and London (07:00-11:00 GMT) sessions only
- **Quantitative Filters**: ATR volatility, Volume confirmation, Trend alignment, Correlation analysis
- **Strict Risk Management**: 1% risk per trade, 3% max daily drawdown, automated trade management
- **Institutional Confluence**: Multiple confirmation factors required for entry

## 📊 Strategy Logic

### Entry Requirements

A trade is executed only when ALL of the following conditions are met:

1. ✅ **Trading Session**: Currently in Asia or London session
2. ✅ **Bias Alignment**: Current timeframe bias aligns with higher timeframe (Daily/4H)
3. ✅ **Liquidity Sweep**: Recent stop run detected at equal highs/lows
4. ✅ **Structure Shift**: MSS or CHOCH confirmation in expected direction
5. ✅ **Entry Zone**: Price retraced to valid Order Block OR Fair Value Gap
6. ✅ **Quantitative Filters**:
   - ATR within normal range (no excessive volatility)
   - Volume above average (institutional activity)
   - Trend aligned with bias
7. ✅ **Minimum Confluences**: At least 3+ confluence factors present

### Trade Management

- **Entry**: At Order Block or FVG boundary
- **Stop Loss**: Beyond OB/structural high-low + buffer
- **Take Profit**: Opposite liquidity pool or 2R minimum
- **Partial TP**: 50% position closed at 1R
- **Break-even**: Stop moved to entry after 1R achieved
- **Max Positions**: 1 open position at a time
- **Max Trades/Session**: 2 trades per session

## 🏗️ Project Structure

```
.
├── config.py                 # Configuration file (adjust settings here)
├── trading_bot.py           # Main trading bot entry point
├── market_structure.py      # Market structure analysis (MSS, CHOCH, bias)
├── liquidity.py            # Liquidity detection (equal highs/lows, sweeps)
├── order_blocks_fvg.py     # Order Blocks and Fair Value Gaps detection
├── fibonacci_ote.py        # Fibonacci OTE zone calculation
├── session_filter.py       # Session timing filters
├── quant_filters.py        # Quantitative filters (ATR, Volume, Trend)
├── risk_management.py      # Risk & trade management
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## 🚀 Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup

1. **Clone or download this repository**

2. **Install dependencies**

```bash
pip install -r requirements.txt
```

3. **Configure broker API** (edit `config.py`)

```python
BROKER_CONFIG = {
    'broker_type': 'MT5',  # or 'OANDA', 'IB', etc.
    'api_key': 'YOUR_API_KEY',
    'api_secret': 'YOUR_API_SECRET',
    'account_id': 'YOUR_ACCOUNT_ID',
    'live_trading': False,  # Set to True for live trading
}
```

## ⚙️ Configuration

All trading parameters are configured in `config.py`. Key settings:

### Risk Management

```python
RISK_CONFIG = {
    'risk_per_trade_pct': 1.0,          # 1% risk per trade
    'max_daily_drawdown_pct': 3.0,      # 3% max daily drawdown
    'max_trades_per_session': 2,        # Max 2 trades per session
    'min_rr_ratio': 2.0                 # Minimum 2:1 Risk:Reward
}
```

### Session Timing (GMT)

```python
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
    }
}
```

### ICT Parameters

```python
ICT_CONFIG = {
    'structure_lookback': 50,           # Bars for structure analysis
    'liquidity_tolerance_pips': 2,      # Tolerance for equal levels
    'ob_min_displacement_pct': 0.15,    # Min % for valid OB
    'fvg_min_gap_pips': 5,              # Min FVG size
    'fib_ote_min': 0.618,               # OTE zone 61.8%
    'fib_ote_max': 0.79                 # OTE zone 79%
}
```

### Quantitative Filters

```python
QUANT_FILTERS = {
    'atr_period': 14,
    'atr_min_multiplier': 0.8,          # Skip if ATR too low
    'atr_max_multiplier': 2.0,          # Skip if ATR too high (news)
    'volume_min_multiplier': 1.0,       # Volume must be > average
    'trend_period': 20,
    'trend_strength_threshold': 0.3
}
```

## 📈 Usage

### Basic Usage

```python
from trading_bot import ICTTradingBot
import pandas as pd

# Initialize the bot
bot = ICTTradingBot()

# Prepare multi-timeframe data
data = {
    'daily': df_daily,   # Daily OHLC data
    '4h': df_4h,         # 4-hour OHLC data
    '1h': df_1h,         # 1-hour OHLC data
    '15m': df_15m,       # 15-minute OHLC data
    '5m': df_5m          # 5-minute OHLC data
}

# Run the strategy
bot.run_strategy(data)
```

### With Live Data (MetaTrader 5)

```python
import MetaTrader5 as mt5
from trading_bot import ICTTradingBot
import pandas as pd

# Initialize MT5
mt5.initialize()

# Login to account
mt5.login(login=YOUR_LOGIN, password="YOUR_PASSWORD", server="YOUR_SERVER")

def fetch_data(symbol, timeframe, bars):
    """Fetch OHLC data from MT5"""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df

# Initialize bot
bot = ICTTradingBot()

# Main loop
while True:
    data = {
        'daily': fetch_data('XAUUSD', mt5.TIMEFRAME_D1, 100),
        '4h': fetch_data('XAUUSD', mt5.TIMEFRAME_H4, 200),
        '1h': fetch_data('XAUUSD', mt5.TIMEFRAME_H1, 500),
        '15m': fetch_data('XAUUSD', mt5.TIMEFRAME_M15, 1000),
        '5m': fetch_data('XAUUSD', mt5.TIMEFRAME_M5, 2000)
    }
    
    bot.run_strategy(data)
    
    # Wait before next iteration (e.g., 5 minutes)
    time.sleep(300)
```

## 🔍 Components Explained

### 1. Market Structure Analyzer

Identifies:
- Swing highs and swing lows
- Market Structure Shifts (MSS) - continuation
- Change of Character (CHOCH) - reversal
- Overall market bias (bullish/bearish/neutral)

```python
from market_structure import MarketStructureAnalyzer, Bias

analyzer = MarketStructureAnalyzer(ICT_CONFIG)
structure = analyzer.get_structure_summary(df)

print(f"Market Bias: {structure['bias'].value}")
print(f"Swing Points: {len(structure['swing_points'])}")
```

### 2. Liquidity Analyzer

Detects:
- Equal highs (buy-side liquidity)
- Equal lows (sell-side liquidity)
- Liquidity sweeps (stop runs)
- Displacement after sweep

```python
from liquidity import LiquidityAnalyzer

analyzer = LiquidityAnalyzer(ICT_CONFIG)
liquidity = analyzer.get_liquidity_summary(df)

print(f"Buy-side pools: {len(liquidity['buy_side_pools'])}")
print(f"Recent sweep: {liquidity['recent_sweep']}")
```

### 3. Order Block Analyzer

Identifies:
- Bullish Order Blocks (last bearish candle before bullish displacement)
- Bearish Order Blocks (last bullish candle before bearish displacement)
- Order Block mitigation (price returning to OB)

```python
from order_blocks_fvg import OrderBlockAnalyzer

analyzer = OrderBlockAnalyzer(ICT_CONFIG)
order_blocks = analyzer.identify_order_blocks(df)

for ob in order_blocks:
    print(f"OB Type: {ob.ob_type.value}, Price: {ob.low}-{ob.high}")
```

### 4. Fair Value Gap Analyzer

Detects:
- Bullish FVGs (gap between candle 1 high and candle 3 low)
- Bearish FVGs (gap between candle 1 low and candle 3 high)
- FVG fills (price returning to gap)

```python
from order_blocks_fvg import FVGAnalyzer

analyzer = FVGAnalyzer(ICT_CONFIG)
fvgs = analyzer.identify_fvgs(df)

for fvg in fvgs:
    print(f"FVG: {fvg.fvg_type.value}, Gap: {fvg.gap_low}-{fvg.gap_high}")
```

### 5. Fibonacci OTE

Calculates:
- Fibonacci retracement levels (0%, 23.6%, 38.2%, 50%, 61.8%, 79%, 100%)
- OTE zone (61.8% - 79% retracement)
- Premium vs Discount zones

```python
from fibonacci_ote import FibonacciOTE

fib = FibonacciOTE(ICT_CONFIG)
levels = fib.get_ote_zone_for_latest_swing(df)

print(f"OTE Zone: {levels.ote_low} - {levels.ote_high}")
```

### 6. Risk Manager

Handles:
- Position sizing (based on % risk)
- Stop loss and take profit calculation
- Partial TP and break-even management
- Daily drawdown limits
- Trade statistics

```python
from risk_management import RiskManager, TradeDirection

risk_mgr = RiskManager(RISK_CONFIG)

trade = risk_mgr.create_trade(
    symbol='XAUUSD',
    direction=TradeDirection.LONG,
    entry_price=2000.00,
    stop_loss=1990.00
)

print(f"Position Size: {trade.position_size} lots")
print(f"Risk Amount: ${trade.risk_amount}")
```

## 📊 Example Output

```
================================================================================
Starting ICT XAUUSD Trading Strategy
================================================================================
2024-01-15 08:30:00 - Market Analysis Complete:
  HTF Bias: bullish
  Current Bias: bullish
  Bias Aligned: True
  Active OBs: 3
  Active FVGs: 2

2024-01-15 08:30:00 - Checking entry conditions...
2024-01-15 08:30:00 - ✅ Entry conditions met! Confluences: 
  ['liquidity_sweep', 'structure_shift', 'ob_or_fvg', 'ote_zone', 'volume_spike', 'atr_valid', 'trend_aligned']

2024-01-15 08:30:05 - ✅ Trade opened: XAUUSD_20240115_083005
   Entry: 2045.50
   Stop Loss: 2040.00
   Take Profit: 2056.00
   Position Size: 0.18 lots
   Risk: $100.00 (1.0%)

Trading Statistics:
  Total Trades: 1
  Win Rate: 0.0%
  Total P&L: $0.00 (0.00%)
  Account Balance: $10000.00
```

## ⚠️ Important Notes

### Risk Warning

**Trading financial instruments carries a high level of risk and may not be suitable for all investors.** 

- Never risk more than you can afford to lose
- Past performance is not indicative of future results
- Always test thoroughly on demo accounts first
- This is educational software - use at your own risk

### Testing Recommendations

1. **Backtest extensively** on historical data (at least 1-2 years)
2. **Paper trade** for 1-3 months on demo account
3. **Start small** when going live (minimum position sizes)
4. **Monitor closely** for the first few weeks
5. **Keep detailed logs** of all trades and system behavior

### Customization

This system is a framework and may need customization based on:

- Your broker's API
- Your risk tolerance
- Market conditions
- Your trading style

## 🔧 Troubleshooting

### Issue: "Volume data not available"

**Solution**: Some data sources don't provide volume for XAUUSD. The system will skip volume filter if data is missing.

### Issue: "No trades being executed"

**Check**:
1. Are you in the correct trading session? (Asia or London)
2. Is bias aligned between timeframes?
3. Are quantitative filters passing?
4. Check logs for specific rejection reasons

### Issue: "Position size too small"

**Solution**: Increase account balance or adjust `risk_per_trade_pct` in config.

## 📚 Resources

### ICT Concepts
- [Inner Circle Trader YouTube Channel](https://www.youtube.com/@InnerCircleTrader)
- ICT Mentorship Program
- Smart Money Concepts Community

### Python Trading
- [TA-Lib Documentation](https://ta-lib.org/)
- [pandas-ta Documentation](https://github.com/twopirllc/pandas-ta)
- [MetaTrader5 Python Package](https://www.mql5.com/en/docs/python_metatrader5)

## 🤝 Contributing

This is an educational project. Feel free to:

- Report bugs
- Suggest improvements
- Share your modifications
- Add new features

## 📝 License

This project is provided for educational purposes. Use at your own risk.

## 🎓 Disclaimer

**This software is for educational and research purposes only.**

- Not financial advice
- No guarantee of profitability
- Author not responsible for trading losses
- Always do your own research
- Consult with a licensed financial advisor

## 📞 Support

For issues or questions:

1. Check this README thoroughly
2. Review the code comments
3. Test on demo account first
4. Keep detailed logs for debugging

---

**Happy Trading! 📈**

*Remember: Consistency and discipline are more important than any strategy.*
