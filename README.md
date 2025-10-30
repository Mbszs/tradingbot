# XAU/USD Trading Bot - ICT + Quantitative Analysis

A robust, professional trading bot for XAU/USD (Gold) that combines **Inner Circle Trader (ICT) concepts** with **quantitative technical analysis** for high-probability trade setups.

## 🎯 Features

### Core Trading Strategy
- **Higher Timeframe Trend Bias**: Uses Daily/4H EMAs (50/200) to define overall market direction
- **Market Structure Analysis**: Detects swing highs/lows, breaks of structure, and trend direction
- **ICT Concepts**:
  - Fair Value Gaps (FVGs) - Bullish and bearish imbalances
  - Order Blocks (OBs) - Institutional supply/demand zones
  - Liquidity Pools - Sweep detection for stop hunts
- **Quantitative Confirmations**:
  - MACD crossover with histogram expansion
  - RSI (14) divergence and threshold filters
  - ATR-based volatility filters
  - Volume/OBV spike detection
  - Multi-MA ribbon alignment (20/50/200 EMA)
- **Price Action Patterns**: Engulfing, pin bars, hammers, shooting stars

### Risk Management
- **Dynamic Position Sizing**: ATR-based position sizing adjusted for volatility
- **Multi-Level Take Profits**: Partial profits at 1.5R and 2.5R
- **Trailing Stops**: Activated at 2R with 1 ATR trail
- **Safety Mechanisms**:
  - Maximum 1-2% risk per trade
  - Cooldown after 3 consecutive losses
  - 3% daily loss limit
  - Maximum 2 concurrent positions

### Advanced Features
- **Session Filters**: Avoid low-liquidity Asian session, prefer London/NY overlap
- **Backtesting Engine**: Comprehensive backtesting with detailed metrics
- **Performance Analytics**: Sharpe ratio, Sortino ratio, Calmar ratio, win rate, profit factor
- **Visualization**: Equity curves, drawdown charts, PnL distribution

## 📁 Project Structure

```
xau-usd-trading-bot/
├── config.py              # Configuration settings
├── indicators.py          # Technical indicators (EMAs, MACD, RSI, ATR, etc.)
├── ict_detector.py        # ICT concepts detection (FVGs, OBs, liquidity)
├── market_structure.py    # Market structure and trend analysis
├── signal_generator.py    # Entry/exit signal generation
├── risk_manager.py        # Risk management and position sizing
├── trading_bot.py         # Main bot orchestrator
├── backtester.py          # Backtesting framework
├── requirements.txt       # Python dependencies
├── example_backtest.py    # Example backtesting script
└── README.md             # This file
```

## 🚀 Quick Start

### 1. Installation

```bash
# Clone or download the repository
cd xau-usd-trading-bot

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Edit `config.py` to customize your strategy parameters:

```python
class TradingConfig:
    # Trading pair
    SYMBOL = "XAU/USD"
    
    # Timeframes
    TIMEFRAME_ENTRY = "1h"      # Entry timeframe
    TIMEFRAME_STRUCTURE = "4h"   # Structure timeframe
    TIMEFRAME_HTF = "1d"         # Higher timeframe for bias
    
    # Risk management
    RISK_PER_TRADE = 0.01        # 1% risk per trade
    STOP_LOSS_ATR = 1.5          # Stop loss in ATR multiples
    
    # ICT settings
    FVG_MIN_SIZE = 0.3           # Minimum FVG size (ATR multiples)
    OB_MIN_BODY_PERCENT = 0.6    # Order block body size threshold
    
    # ... more settings in config.py
```

### 3. Backtesting

Create a backtesting script (see `example_backtest.py`):

```python
from config import TradingConfig
from backtester import Backtester
import pandas as pd

# Load your historical data
df_1h = pd.read_csv('xauusd_1h.csv')  # Your 1H data
df_4h = pd.read_csv('xauusd_4h.csv')  # Your 4H data

# Initialize backtester
config = TradingConfig()
backtester = Backtester(config)

# Run backtest
results = backtester.run_backtest(df_1h, df_4h, initial_capital=10000)

# Print and plot results
backtester.print_results(results)
backtester.plot_results(results, save_path='backtest_results.png')
backtester.save_results(results, 'backtest_results.json')
```

### 4. Live/Paper Trading

```python
from config import TradingConfig
from trading_bot import XAUUSDTradingBot

# Initialize bot
config = TradingConfig()
bot = XAUUSDTradingBot(
    config, 
    initial_capital=10000,
    live_mode=False  # Set to True for live trading
)

# Run bot (updates every hour for 1H timeframe)
bot.run(update_interval=3600)
```

## 📊 Strategy Logic Flow

```
1. Higher Timeframe Analysis (Daily/4H)
   ├─ Check EMA 50/200 for trend direction
   └─ Only trade WITH the HTF trend

2. Market Structure (1H)
   ├─ Detect swing highs/lows
   ├─ Identify structure breaks
   └─ Determine current trend

3. ICT Zone Detection
   ├─ Fair Value Gaps (FVGs)
   ├─ Order Blocks (OBs)
   └─ Liquidity Pools

4. Entry Confirmation (All must align)
   ├─ Price at ICT zone OR strong price action
   ├─ MACD crossover or bullish/bearish
   ├─ RSI > 50 (long) or < 50 (short)
   ├─ ATR filter (avoid low volatility)
   ├─ Volume spike confirmation
   ├─ MA ribbon aligned
   └─ Price within 2 ATR of 50 EMA

5. Risk Management
   ├─ Calculate position size (ATR-based)
   ├─ Set stop loss (1.5 ATR)
   ├─ Set take profits (1.5R, 2.5R)
   └─ Activate trailing stop at 2R

6. Trade Management
   ├─ Partial close at TP1 (33%)
   ├─ Partial close at TP2 (33%)
   ├─ Trail remaining 34% with 1 ATR
   └─ Monitor for exit signals
```

## 🎯 Target Performance Metrics

Based on robust parameter settings:

- **Win Rate**: 55-65% (conservative, high-quality setups)
- **Profit Factor**: 1.5-2.5+
- **Average Risk:Reward**: 2.0-3.0
- **Max Drawdown**: < 15%
- **Sharpe Ratio**: > 1.5
- **Trade Frequency**: 2-5 trades per week (quality over quantity)

## ⚙️ Data Requirements

The bot requires OHLCV data with the following structure:

```python
pd.DataFrame({
    'timestamp': datetime,  # Timestamp for each candle
    'open': float,         # Opening price
    'high': float,         # Highest price
    'low': float,          # Lowest price
    'close': float,        # Closing price
    'volume': float        # Volume
})
```

### Data Sources

**For Backtesting:**
- Download from TradingView, Investing.com, or MetaTrader
- Use `yfinance` for free data: `yf.download("GC=F", interval="1h")`

**For Live Trading:**
- MetaTrader 5: `mt5.copy_rates_from_pos()`
- CCXT (crypto exchanges): `exchange.fetch_ohlcv()`
- Your broker's API

Implement the `load_historical_data()` method in `trading_bot.py` with your data source.

## 🔧 Customization

### Adjusting Strategy Parameters

**More Conservative (Lower Risk, Lower Frequency):**
```python
config.RISK_PER_TRADE = 0.005      # 0.5% per trade
config.FVG_MIN_SIZE = 0.5           # Larger FVGs only
config.MAX_DISTANCE_FROM_MA = 1.5   # Closer to MA
```

**More Aggressive (Higher Risk, Higher Frequency):**
```python
config.RISK_PER_TRADE = 0.02        # 2% per trade
config.FVG_MIN_SIZE = 0.2           # Smaller FVGs
config.MAX_DISTANCE_FROM_MA = 3.0   # Further from MA
```

### Adding Custom Indicators

Add your indicators in `indicators.py`:

```python
@staticmethod
def calculate_custom_indicator(data: pd.Series) -> pd.Series:
    # Your indicator logic
    return result
```

Then use in `signal_generator.py`:

```python
custom_ind = self.indicators.calculate_custom_indicator(df['close'])
```

## 📈 Backtesting Example Output

```
============================================================
BACKTEST RESULTS
============================================================

Overall Performance:
  Initial Capital:     $10,000.00
  Final Capital:       $13,450.00
  Total Return:        34.50%
  Max Drawdown:        8.20%

Trade Statistics:
  Total Trades:        45
  Winning Trades:      28
  Losing Trades:       17
  Win Rate:            62.22%
  Profit Factor:       2.15

Risk Metrics:
  Average Win:         $185.50
  Average Loss:        $95.30
  Average R:R:         2.35
  Expectancy:          $76.67

Advanced Metrics:
  Sharpe Ratio:        1.85
  Sortino Ratio:       2.42
  Calmar Ratio:        4.21

Trade Duration:
  Avg Duration:        18.5 hours

Streaks:
  Max Win Streak:      6
  Max Loss Streak:     3

============================================================
```

## ⚠️ Important Notes

### Before Live Trading

1. **Thoroughly backtest** on at least 2 years of historical data
2. **Paper trade** for at least 1-2 months to verify performance
3. **Start small** with minimum position sizes
4. **Monitor closely** for the first few weeks
5. **Implement broker connection** in `execute_trade()` and `close_trade()` methods

### Risk Warnings

- **Trading involves substantial risk** of loss
- **Past performance does not guarantee future results**
- This bot is provided as-is without warranties
- **Always test thoroughly** before risking real capital
- **Never risk more than you can afford to lose**

### Required Implementations

Before using in production, you MUST implement:

1. **Data Loading**: `load_historical_data()` in `trading_bot.py`
2. **Trade Execution**: `execute_trade()` in `trading_bot.py`
3. **Trade Closing**: `close_trade()` in `trading_bot.py`
4. **Broker Connection**: Your specific broker's API

## 🛠️ Troubleshooting

### Common Issues

**"Insufficient data" warning:**
- Ensure you have at least 250+ candles of historical data
- The bot needs data to calculate 200 EMA and other indicators

**No signals generated:**
- Check if HTF trend is clear (not ranging/neutral)
- Verify ATR is above minimum threshold
- Ensure data quality (no gaps, correct format)

**High drawdown in backtest:**
- Reduce `RISK_PER_TRADE`
- Increase `STOP_LOSS_ATR`
- Tighten entry filters (e.g., require more confirmations)

## 📚 ICT Concepts Explained

### Fair Value Gaps (FVGs)
Imbalances in price where there's inefficient trading (gap between candles). Price tends to return to fill these gaps.

### Order Blocks (OBs)
The last candle before a strong impulsive move. Represents institutional accumulation/distribution zones.

### Liquidity Pools
Areas where stop losses cluster (swing highs/lows, equal highs/lows). Often targeted before true directional moves.

### Market Structure
Pattern of higher highs/higher lows (uptrend) or lower highs/lower lows (downtrend). Breaks indicate potential reversals.

## 🤝 Contributing

Improvements and contributions are welcome! Areas for enhancement:
- Additional ICT concepts (Breaker blocks, Mitigation blocks)
- Machine learning for pattern recognition
- Multi-symbol support
- Web dashboard for monitoring
- Telegram/Discord notifications

## 📄 License

This project is provided as-is for educational and research purposes.

## 📞 Support

For questions or issues:
1. Check the code comments and documentation
2. Review the example scripts
3. Test with paper trading first

---

**Disclaimer**: This trading bot is for educational purposes. Use at your own risk. Always backtest thoroughly and start with paper trading before risking real capital.
