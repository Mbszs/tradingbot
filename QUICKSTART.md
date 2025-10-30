# Quick Start Guide - XAU/USD Trading Bot

Get your trading bot up and running in 5 minutes!

## Step 1: Install Dependencies (1 minute)

```bash
pip install -r requirements.txt
```

## Step 2: Test the System (2 minutes)

Run the example backtest with sample data:

```bash
python example_backtest.py
```

This will:
- Generate sample price data
- Run a complete backtest
- Display performance metrics
- Save results to `results/` folder

Expected output:
```
Total Trades: 30-50
Win Rate: 55-65%
Total Return: 15-35%
Max Drawdown: 5-15%
```

## Step 3: Configure Your Strategy (1 minute)

Edit `config.py` to customize:

```python
# Quick settings to adjust
RISK_PER_TRADE = 0.01          # 1% risk per trade
TIMEFRAME_ENTRY = "1h"         # Entry timeframe
TIMEFRAME_HTF = "1d"           # Higher timeframe for bias
FVG_MIN_SIZE = 0.3             # Fair Value Gap minimum size
ENABLE_SESSION_FILTER = True   # Filter trading sessions
```

## Step 4: Add Your Data Source (1 minute)

Choose your data source and implement in `trading_bot.py`:

### Option A: CSV Files
```python
def load_historical_data(self, symbol, timeframe, lookback_periods=500):
    df = pd.read_csv(f'data/{symbol}_{timeframe}.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    return df
```

### Option B: MetaTrader 5
```python
import MetaTrader5 as mt5

def load_historical_data(self, symbol, timeframe, lookback_periods=500):
    mt5.initialize()
    timeframe_map = {'1h': mt5.TIMEFRAME_H1, '4h': mt5.TIMEFRAME_H4, '1d': mt5.TIMEFRAME_D1}
    rates = mt5.copy_rates_from_pos(symbol, timeframe_map[timeframe], 0, lookback_periods)
    df = pd.DataFrame(rates)
    df['timestamp'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('timestamp', inplace=True)
    return df[['open', 'high', 'low', 'close', 'tick_volume']].rename(columns={'tick_volume': 'volume'})
```

### Option C: yfinance (Free Data)
```python
import yfinance as yf

def load_historical_data(self, symbol, timeframe, lookback_periods=500):
    ticker = yf.Ticker("GC=F")  # Gold futures
    period_map = {'1h': '60d', '4h': '90d', '1d': '2y'}
    interval_map = {'1h': '1h', '4h': '1h', '1d': '1d'}
    
    df = ticker.history(period=period_map.get(timeframe, '60d'), 
                       interval=interval_map.get(timeframe, '1h'))
    df.columns = [col.lower() for col in df.columns]
    return df[['open', 'high', 'low', 'close', 'volume']]
```

## Step 5: Run Your First Real Backtest

With your real data:

```python
from config import TradingConfig
from backtester import Backtester
import pandas as pd

# Load your data
df_1h = pd.read_csv('your_1h_data.csv')  # Your actual data
df_4h = pd.read_csv('your_4h_data.csv')  # Your actual data

# Run backtest
config = TradingConfig()
backtester = Backtester(config)
results = backtester.run_backtest(df_1h, df_4h, initial_capital=10000)

# View results
backtester.print_results(results)
backtester.plot_results(results)
```

## Common Next Steps

### Paper Trading
```python
from trading_bot import XAUUSDTradingBot
from config import TradingConfig

config = TradingConfig()
bot = XAUUSDTradingBot(config, initial_capital=10000, live_mode=False)
bot.run(update_interval=3600)  # Update every hour
```

### Optimize Parameters
```bash
python example_backtest.py
# Choose option 2 for parameter optimization
```

### Go Live (After Thorough Testing!)
```python
# 1. Implement execute_trade() and close_trade() in trading_bot.py
# 2. Test in paper trading for 1+ month
# 3. Start with small capital
bot = XAUUSDTradingBot(config, initial_capital=1000, live_mode=True)
bot.run()
```

## Troubleshooting

**"Insufficient data" error:**
- Ensure at least 250+ candles of historical data
- Check data format (OHLCV with timestamp)

**No signals generated:**
- Check if market is in a clear trend (not ranging)
- Verify ATR is above minimum threshold
- Review config settings (might be too strict)

**Import errors:**
- Run `pip install -r requirements.txt` again
- Check Python version (3.8+)

## File Structure Quick Reference

```
├── config.py               # ⚙️  Configure everything here
├── trading_bot.py          # 🤖 Main bot (implement data loading here)
├── backtester.py           # 📊 Backtesting engine
├── signal_generator.py     # 📡 Signal generation logic
├── risk_manager.py         # 💰 Risk management
├── ict_detector.py         # 🎯 ICT concepts (FVGs, OBs, liquidity)
├── market_structure.py     # 📈 Trend and structure analysis
├── indicators.py           # 📉 Technical indicators
├── example_backtest.py     # 🧪 Run this first!
├── example_live_trading.py # 🚀 Paper/live trading examples
└── README.md              # 📖 Full documentation
```

## Key Concepts Reminder

**ICT Concepts:**
- **FVG (Fair Value Gap)**: Price imbalances that tend to get filled
- **Order Block**: Last candle before strong move (institutional zones)
- **Liquidity**: Stop loss clusters that get swept before real moves

**Strategy Flow:**
1. Higher timeframe defines bias (Daily/4H EMAs)
2. Wait for price to reach ICT zone (FVG or OB)
3. Confirm with multiple indicators (MACD, RSI, Volume)
4. Check price action (engulfing, pin bar)
5. Enter with proper risk management
6. Scale out at TP1, TP2, trail the rest

## Performance Tips

**For Better Win Rate:**
- Increase `FVG_MIN_SIZE` (only take larger FVGs)
- Require `MACD_HISTOGRAM_EXPANSION = True`
- Reduce `MAX_DISTANCE_FROM_MA` (enter closer to EMA)

**For More Trades:**
- Decrease `FVG_MIN_SIZE`
- Increase `MAX_DISTANCE_FROM_MA`
- Set `ENABLE_SESSION_FILTER = False`

**For Lower Drawdown:**
- Reduce `RISK_PER_TRADE` to 0.5%
- Increase `STOP_LOSS_ATR` to 2.0
- Enable `MAX_CONSECUTIVE_LOSSES` cooldown

## Support

Having issues? Check:
1. ✅ All dependencies installed
2. ✅ Data format is correct (OHLCV with timestamp)
3. ✅ Sufficient historical data (250+ candles)
4. ✅ Python 3.8 or higher
5. ✅ Example backtest runs successfully

## Next Steps

1. ✅ Run `example_backtest.py` with sample data
2. ⬜ Load your own historical data
3. ⬜ Backtest on 2+ years of data
4. ⬜ Optimize parameters for your market
5. ⬜ Paper trade for 1+ month
6. ⬜ Go live with small capital

---

**Remember**: Always backtest thoroughly and paper trade before risking real money!

Good luck with your trading! 🚀📈
