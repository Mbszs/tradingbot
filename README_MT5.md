# XAU/USD Trading Bot for MetaTrader 5

**Professional-grade trading bot combining ICT concepts with quantitative analysis, specifically designed for MetaTrader 5.**

---

## 🎯 What's This?

A fully automated trading system for Gold (XAU/USD) that:
- ✅ **Connects directly to MetaTrader 5** - No manual trading needed
- ✅ **Uses ICT concepts** - Fair Value Gaps, Order Blocks, Liquidity sweeps
- ✅ **Applies quantitative filters** - MACD, RSI, ATR, Volume confirmations
- ✅ **Manages risk dynamically** - ATR-based position sizing, partial profits, trailing stops
- ✅ **Includes backtesting** - Test on years of MT5 historical data
- ✅ **Ready for live trading** - Full trade execution and management

---

## 🚀 Quick Start (10 Minutes)

### 1. Install Requirements (2 minutes)

```bash
pip install -r requirements.txt
```

This installs:
- MetaTrader5 Python library
- pandas, numpy for data processing
- matplotlib for charts

### 2. Test MT5 Connection (2 minutes)

**Make sure MT5 is running and you're logged in!**

```bash
python example_mt5_live.py
```

Select option **2** (Test connection)

Expected output:
```
✓ Connected successfully!
Account Balance: $10,000.00
Symbol: XAUUSD
```

### 3. Run Your First Backtest (5 minutes)

```bash
python example_mt5_backtest.py
```

This will:
1. Download historical data from MT5
2. Run comprehensive backtest
3. Show performance metrics
4. Save results and charts

### 4. Start Paper Trading (1 minute)

```bash
python example_mt5_live.py
```

Select option **1**, then choose **Paper Trading** mode.

The bot will now monitor markets and generate signals (without risking money).

---

## 📁 Project Structure

```
xau-usd-trading-bot/
│
├── Core MT5 Files
│   ├── mt5_connector.py       # 🔌 MT5 connection & trading
│   ├── trading_bot_mt5.py     # 🤖 Main MT5 bot
│   ├── example_mt5_live.py    # 🚀 Run live/paper trading
│   └── example_mt5_backtest.py # 📊 Backtest with MT5 data
│
├── Strategy Modules
│   ├── config.py              # ⚙️ All settings
│   ├── signal_generator.py    # 📡 Entry/exit signals
│   ├── ict_detector.py        # 🎯 ICT concepts
│   ├── market_structure.py    # 📈 Trend & structure
│   ├── indicators.py          # 📉 Technical indicators
│   ├── risk_manager.py        # 💰 Risk management
│   └── backtester.py          # 🧪 Backtesting engine
│
└── Documentation
    ├── MT5_SETUP_GUIDE.md     # 📖 Complete MT5 setup
    ├── MT5_QUICK_REFERENCE.md # ⚡ Quick command reference
    ├── README.md              # 📚 Full documentation
    └── QUICKSTART.md          # 🏃 5-minute guide
```

---

## 🎓 Usage Examples

### Example 1: Basic Backtesting

```python
from mt5_connector import MT5Connector
from backtester import Backtester
from config import TradingConfig

# Connect to MT5
mt5 = MT5Connector(symbol="XAUUSD")
mt5.connect()

# Get historical data
df_1h = mt5.get_historical_data('1h', bars=5000)
df_4h = mt5.get_historical_data('4h', bars=2000)

# Run backtest
config = TradingConfig()
backtester = Backtester(config)
results = backtester.run_backtest(df_1h, df_4h, initial_capital=10000)

# View results
backtester.print_results(results)
backtester.plot_results(results)

mt5.disconnect()
```

### Example 2: Paper Trading

```python
from mt5_connector import MT5Connector
from trading_bot_mt5 import XAUUSDTradingBotMT5
from config import TradingConfig

# Connect
mt5 = MT5Connector(symbol="XAUUSD", magic_number=234000)
mt5.connect()

# Initialize bot
config = TradingConfig()
bot = XAUUSDTradingBotMT5(config, mt5, live_mode=False)

# Run (updates every hour for 1H timeframe)
bot.run(update_interval=3600)
```

### Example 3: Live Trading (After Testing!)

```python
from mt5_connector import MT5Connector
from trading_bot_mt5 import XAUUSDTradingBotMT5
from config import TradingConfig

# Connect
mt5 = MT5Connector(symbol="XAUUSD", magic_number=234000)
mt5.connect()

# Configure for live
config = TradingConfig()
config.RISK_PER_TRADE = 0.005  # Start with 0.5%
config.MAX_OPEN_TRADES = 1     # One position at a time

# Initialize bot in LIVE mode
bot = XAUUSDTradingBotMT5(config, mt5, live_mode=True)

# Run
bot.run(update_interval=3600)
```

### Example 4: Manual MT5 Operations

```python
from mt5_connector import MT5Connector

mt5 = MT5Connector(symbol="XAUUSD")
mt5.connect()

# Get current price
price = mt5.get_current_price()
print(f"Current bid: ${price['bid']:.2f}")

# Open position manually
ticket = mt5.open_position(
    position_type='long',
    volume=0.01,
    stop_loss=1950.0,
    take_profit=1980.0,
    comment="Manual entry"
)

# Get open positions
positions = mt5.get_open_positions()
for pos in positions:
    print(f"Position {pos['ticket']}: {pos['type']} {pos['volume']} lots")

# Close position
mt5.close_position(ticket)

mt5.disconnect()
```

---

## ⚙️ Configuration

Edit `config.py` to customize the strategy:

### Symbol Settings
```python
SYMBOL = "XAUUSD"  # Adjust for your broker (might be "GOLD", "XAU/USD")
```

### Timeframes
```python
TIMEFRAME_ENTRY = "1h"      # Entry timeframe
TIMEFRAME_STRUCTURE = "4h"   # Market structure
TIMEFRAME_HTF = "1d"        # Higher timeframe bias
```

### Risk Management
```python
RISK_PER_TRADE = 0.01       # 1% risk per trade
MAX_OPEN_TRADES = 2         # Maximum concurrent positions
STOP_LOSS_ATR = 1.5         # Stop loss in ATR multiples
```

### ICT Settings
```python
FVG_MIN_SIZE = 0.3          # Minimum Fair Value Gap size
OB_MIN_BODY_PERCENT = 0.6   # Order Block body size threshold
LIQUIDITY_LOOKBACK = 20     # Candles to look for liquidity
```

### Session Filters
```python
ENABLE_SESSION_FILTER = True
AVOID_ASIAN_SESSION = True   # Skip low-liquidity hours
LONDON_OPEN = 8              # 08:00 UTC
NY_OPEN = 13                 # 13:00 UTC
```

---

## 🎯 Strategy Overview

### Entry Requirements (ALL must be met)

**LONG Position:**
1. ✅ Higher timeframe bullish (price > 50 & 200 EMA on Daily)
2. ✅ Market structure bullish or neutral
3. ✅ Price at ICT zone (Fair Value Gap OR Order Block)
4. ✅ MACD bullish (above signal line or crossover)
5. ✅ RSI > 50 (momentum confirmation)
6. ✅ ATR above minimum (avoid low volatility)
7. ✅ Volume spike (confirmation of move)
8. ✅ Within 2 ATR of 50 EMA (not overextended)

**SHORT Position:**
- Same logic, inverted

### Risk Management Flow

```
Entry → Calculate lot size based on ATR
     ↓
Set Stop Loss (1.5 ATR from entry)
     ↓
Set Take Profit 1 (1.5R - close 33%)
     ↓
If TP1 hit → Move SL to breakeven
     ↓
Set Take Profit 2 (2.5R - close 33%)
     ↓
If TP2 hit → Trail remaining 34% with 1 ATR
     ↓
Exit via trailing stop or structure break
```

---

## 📊 Expected Performance

Based on backtests and design:

| Metric | Target |
|--------|--------|
| Win Rate | 55-65% |
| Profit Factor | 1.5-2.5+ |
| Average R:R | 2.0-3.0 |
| Max Drawdown | <15% |
| Sharpe Ratio | >1.5 |
| Trades/Week | 2-5 |

*Actual results vary based on market conditions and settings*

---

## 🔧 MT5-Specific Features

### Automatic Trade Execution
- Opens positions via MT5 API
- Sets SL/TP automatically
- Modifies positions as targets hit
- Partial closes for TP1/TP2
- Implements trailing stops

### Position Management
- Tracks positions by magic number
- Syncs with MT5 positions
- Handles manual interventions gracefully
- Updates SL/TP dynamically

### Data Management
- Downloads historical data from MT5
- Real-time price updates
- Symbol information retrieval
- Account balance monitoring

### Safety Features
- Magic number isolation (234000 default)
- Won't interfere with other EAs
- Tracks only bot's own trades
- Emergency stop on errors

---

## 🛠️ Troubleshooting

### "Failed to connect to MT5"

**Fix:**
1. Make sure MT5 terminal is running
2. Ensure you're logged into an account
3. Enable algo trading: Tools → Options → Expert Advisors
4. Check "Allow algorithmic trading"

### "Symbol XAUUSD not found"

**Fix:**
1. Add XAUUSD to Market Watch (Ctrl+U)
2. Check your broker's symbol name:
   ```python
   import MetaTrader5 as mt5
   mt5.initialize()
   symbols = [s.name for s in mt5.symbols_get() if 'gold' in s.name.lower()]
   print(symbols)  # Find correct name
   ```
3. Update `config.py` with correct symbol

### "Trade execution failed"

**Fix:**
1. Check account has sufficient margin
2. Verify minimum lot size (usually 0.01)
3. Check spread isn't too wide during off-hours
4. Ensure market is open (Gold: Sun 23:00 - Fri 22:00 GMT)

### More Help

See `MT5_SETUP_GUIDE.md` for comprehensive troubleshooting.

---

## 📈 Getting Started Roadmap

### Week 1: Setup & Testing
- [ ] Install requirements
- [ ] Test MT5 connection
- [ ] Run backtest on 1+ year data
- [ ] Review strategy logic
- [ ] Understand all parameters

### Week 2-5: Paper Trading
- [ ] Run bot in paper mode
- [ ] Monitor daily
- [ ] Analyze generated signals
- [ ] Review all trades
- [ ] Optimize parameters if needed

### Week 6+: Live Trading (Optional)
- [ ] Start with demo account
- [ ] Use conservative settings (0.5% risk)
- [ ] Monitor closely
- [ ] Keep detailed journal
- [ ] Scale gradually

---

## 🔐 Security Best Practices

### Before Live Trading

✅ **Demo Account First**
- Run bot on demo for 1+ month
- Verify behavior matches expectations
- Test during different market conditions

✅ **Start Conservative**
```python
RISK_PER_TRADE = 0.005        # 0.5% per trade
MAX_OPEN_TRADES = 1           # Single position
STOP_LOSS_ATR = 2.0           # Wider stops
```

✅ **Monitor Regularly**
- Check bot status daily
- Review trades weekly
- Analyze performance monthly

✅ **Use VPS**
- Recommended for 24/7 operation
- Windows VPS best for MT5
- Low latency to broker

### Password Security

Never hardcode credentials:

```python
# ❌ DON'T DO THIS
mt5.connect(login=12345, password="mypassword", server="Broker-Demo")

# ✅ DO THIS
import os
mt5.connect(
    login=int(os.getenv('MT5_LOGIN')),
    password=os.getenv('MT5_PASSWORD'),
    server=os.getenv('MT5_SERVER')
)
```

---

## 📚 Documentation

- **MT5_SETUP_GUIDE.md** - Complete MT5 setup instructions
- **MT5_QUICK_REFERENCE.md** - One-page command reference
- **README.md** - Full strategy documentation
- **QUICKSTART.md** - 5-minute quick start
- **PROJECT_SUMMARY.md** - Project overview

---

## 💡 Tips for Success

### 1. Backtest Thoroughly
- Use 2+ years of data
- Test different market conditions
- Verify win rate >55%, profit factor >1.5

### 2. Understand the Strategy
- Read all documentation
- Study each module
- Know why each filter exists
- Understand ICT concepts

### 3. Start Small
- Begin with 0.5% risk
- Use demo account first
- Single position limit
- Monitor closely

### 4. Keep Learning
- Analyze every trade
- Keep a trading journal
- Note market conditions
- Refine parameters

### 5. Be Patient
- Good trades are rare
- Quality over quantity
- Don't force trades
- Trust the process

---

## ⚠️ Disclaimer

**IMPORTANT:**
- Trading involves substantial risk of loss
- Past performance does not guarantee future results
- This software is provided as-is without warranties
- Always test on demo before live
- Never risk more than you can afford to lose
- Monitor automated systems regularly

---

## 🎉 Ready to Start!

You now have a professional MT5 trading bot that:
- ✅ Connects directly to MetaTrader 5
- ✅ Implements proven ICT + quantitative concepts
- ✅ Manages risk intelligently
- ✅ Executes trades automatically
- ✅ Is ready for backtesting and live trading

**Next Steps:**
1. Run `python example_mt5_live.py` (option 2) to test connection
2. Run `python example_mt5_backtest.py` for backtest
3. Read `MT5_SETUP_GUIDE.md` for detailed setup
4. Start paper trading for 1+ month

---

**Good luck with your MT5 trading! 🚀📈**

*Questions? Check the docs or review the example scripts.*
