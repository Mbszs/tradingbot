# MT5 Setup Guide - XAU/USD Trading Bot

Complete guide to set up and run the trading bot with MetaTrader 5.

---

## 📋 Prerequisites

### 1. MetaTrader 5 Installation

**Download MT5:**
- Visit your broker's website
- Download MetaTrader 5 for your platform (Windows/Mac/Linux)
- Install and create a demo/live account

**Popular MT5 Brokers for Gold Trading:**
- IC Markets
- Pepperstone
- XM
- FXCM
- Admiral Markets
- Many others...

### 2. Python Requirements

```bash
# Install Python 3.8 or higher
python --version  # Should be 3.8+

# Install dependencies
pip install -r requirements.txt
```

**Key Package:** `MetaTrader5` Python library
```bash
pip install MetaTrader5
```

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Verify MT5 Connection

```bash
python example_mt5_live.py
# Choose option 2: Test MT5 connection
```

If successful, you should see:
```
✓ Connected successfully!
Account Balance: $10,000.00
Symbol: XAUUSD
```

### Step 2: Run a Backtest

```bash
python example_mt5_backtest.py
```

This will:
1. Connect to MT5
2. Download historical data
3. Run backtest
4. Display results

### Step 3: Paper Trading

```bash
python example_mt5_live.py
# Choose option 1: Run trading bot
# Select: Paper Trading mode
```

---

## 🔧 Detailed Setup

### Windows Setup

1. **Install MT5**
   - Download from your broker
   - Complete installation
   - Login to your account

2. **Enable Algo Trading**
   - Open MT5
   - Tools → Options → Expert Advisors
   - Check "Allow algorithmic trading"
   - Check "Allow DLL imports"

3. **Add XAUUSD to Market Watch**
   - View → Market Watch (Ctrl+M)
   - Right-click → Symbols
   - Search "XAUUSD" or "GOLD"
   - Show symbol

4. **Install Python Package**
   ```bash
   pip install MetaTrader5
   ```

5. **Test Connection**
   ```bash
   python example_mt5_live.py
   # Option 2 - Test connection
   ```

### Mac/Linux Setup

1. **Install Wine (for MT5)**
   ```bash
   # Mac
   brew install wine-stable
   
   # Linux
   sudo apt-get install wine
   ```

2. **Install MT5 via Wine**
   ```bash
   wine mt5setup.exe
   ```

3. **Install MT5 Python Package**
   ```bash
   pip install MetaTrader5
   ```

4. **Run with Wine**
   - Start MT5 under Wine
   - Ensure it's running before starting bot
   - Python will connect to the Wine instance

**Alternative:** Use Windows VPS for reliable 24/7 operation

---

## 📊 Configuration

### Basic Configuration (`config.py`)

```python
# Symbol
SYMBOL = "XAUUSD"  # Or "GOLD", "XAU/USD" depending on broker

# Timeframes
TIMEFRAME_ENTRY = "1h"      # Entry signals
TIMEFRAME_STRUCTURE = "4h"   # Market structure
TIMEFRAME_HTF = "1d"        # Higher timeframe bias

# Risk Management
RISK_PER_TRADE = 0.01       # 1% per trade
MAX_OPEN_TRADES = 2         # Maximum concurrent positions

# Stop Loss & Take Profit
STOP_LOSS_ATR = 1.5         # Stop loss distance
TAKE_PROFIT_1 = 1.5         # First TP (33%)
TAKE_PROFIT_2 = 2.5         # Second TP (33%)
```

### MT5-Specific Settings

```python
# In your script
from mt5_connector import MT5Connector

mt5 = MT5Connector(
    symbol="XAUUSD",        # Your broker's symbol name
    magic_number=234000     # Unique ID for bot's trades
)

# Connect with credentials (optional)
mt5.connect(
    login=12345678,
    password="YourPassword",
    server="YourBroker-Demo"
)
```

---

## 🎯 Running the Bot

### Option 1: Interactive Mode

```bash
python example_mt5_live.py
```

Follow the prompts:
1. Connection verification
2. Configuration review
3. Mode selection (Paper/Live)
4. Confirmation

### Option 2: Script Mode

Create `run_bot.py`:

```python
from config import TradingConfig
from trading_bot_mt5 import XAUUSDTradingBotMT5
from mt5_connector import MT5Connector

# Connect to MT5
mt5 = MT5Connector(symbol="XAUUSD", magic_number=234000)
if not mt5.connect():
    print("Failed to connect")
    exit(1)

# Initialize bot
config = TradingConfig()
bot = XAUUSDTradingBotMT5(config, mt5, live_mode=False)  # False = paper trading

# Run continuously
bot.run(update_interval=3600)  # Update every hour
```

Then run:
```bash
python run_bot.py
```

### Option 3: Background Service (24/7)

**Linux/Mac:**
```bash
# Run in background
nohup python run_bot.py > bot.log 2>&1 &

# Check status
ps aux | grep run_bot

# Stop
kill <pid>
```

**Windows:**
- Use Task Scheduler
- Or run in screen/tmux
- Or use Windows Service wrapper

---

## 🔍 Monitoring

### Real-Time Logs

```bash
# Watch logs in real-time
tail -f logs/trading_bot_mt5.log
```

### MT5 Terminal

- Open Positions: View → Toolbox → Trade (Ctrl+T)
- History: View → Toolbox → History
- Check for bot's magic number: 234000

### Account Statistics

The bot logs status every update:
```
STATUS UPDATE
============================================================
Account Balance:  $10,234.50
Account Equity:   $10,456.78
Open Positions:   1
Total Trades:     15
Win Rate:         60.0%
Profit Factor:    2.15
```

---

## ⚙️ Troubleshooting

### Issue: "Failed to connect to MT5"

**Solutions:**
1. Make sure MT5 is running
2. Check you're logged into an account
3. Enable algo trading (Tools → Options → Expert Advisors)
4. Run as administrator (Windows)
5. Check firewall settings

**Test Command:**
```python
import MetaTrader5 as mt5
print(mt5.initialize())  # Should print True
```

### Issue: "Symbol XAUUSD not found"

**Solutions:**
1. Add XAUUSD to Market Watch
2. Check your broker's symbol name (might be "GOLD", "XAU/USD", etc.)
3. Update config.py with correct symbol name

**Find Symbol:**
```python
import MetaTrader5 as mt5
mt5.initialize()
symbols = mt5.symbols_get()
gold_symbols = [s.name for s in symbols if 'gold' in s.name.lower() or 'xau' in s.name.lower()]
print(gold_symbols)
```

### Issue: "Insufficient data"

**Solutions:**
1. MT5 needs to download history first
2. Open a chart for XAUUSD in MT5
3. Scroll back to load more history
4. Wait a few minutes for data to download

### Issue: "Trade execution failed"

**Solutions:**
1. Check account has sufficient margin
2. Verify minimum lot size (usually 0.01)
3. Check spread isn't too wide
4. Ensure market is open (Gold trades 24/5)
5. Check for trade restrictions (day trading limits, etc.)

### Issue: Bot stops unexpectedly

**Solutions:**
1. Check logs: `logs/trading_bot_mt5.log`
2. Ensure MT5 stays running
3. Check internet connection
4. Verify account credentials
5. Use VPS for stability

---

## 📈 Backtesting with MT5 Data

### Full Backtest

```bash
python example_mt5_backtest.py
# Option 1: Full backtest
```

Downloads all available data and runs comprehensive backtest.

### Quick Backtest (Recent Data)

```bash
python example_mt5_backtest.py
# Option 2: Quick backtest
```

Tests on last 3 months only - faster for quick validation.

### Parameter Optimization

```bash
python example_mt5_backtest.py
# Option 1: Full backtest
# Then select: Yes for optimization
```

Tests multiple parameter combinations to find optimal settings.

---

## 🔐 Security Best Practices

### 1. Start with Demo Account
- **Always** test with demo first
- Run for at least 1 month
- Verify bot behaves as expected

### 2. Use Strong Passwords
- Never hardcode passwords in scripts
- Use environment variables or config files
- Add credentials file to .gitignore

### 3. Set Trade Limits
```python
# In config.py
RISK_PER_TRADE = 0.01          # Start conservative
MAX_OPEN_TRADES = 1            # Limit exposure
MAX_DAILY_LOSS = 0.03          # 3% daily stop
```

### 4. Monitor Regularly
- Check bot status daily
- Review trades and performance
- Watch for unexpected behavior

### 5. Use VPS (Recommended)
- Reliable 24/7 operation
- Low latency to broker
- No local computer issues
- Windows VPS recommended (~$10-20/month)

---

## 💡 Tips for Success

### Before Live Trading

✅ Backtest on 2+ years of data
✅ Win rate > 55%
✅ Profit factor > 1.5
✅ Max drawdown < 15%
✅ Paper trade 1+ month successfully
✅ Understand every part of the strategy
✅ Start with small capital

### Trading Hours

**Gold (XAUUSD) Trading:**
- Opens: Sunday 23:00 GMT
- Closes: Friday 22:00 GMT
- Most active: London + NY sessions

**Bot Session Filters:**
- Enabled by default
- Avoids Asian low-liquidity periods
- Focuses on London/NY overlap

### Position Management

**Recommended Settings:**
```python
# Conservative (recommended for beginners)
RISK_PER_TRADE = 0.005         # 0.5%
STOP_LOSS_ATR = 2.0            # Wider stops
MAX_OPEN_TRADES = 1            # Single position

# Moderate
RISK_PER_TRADE = 0.01          # 1%
STOP_LOSS_ATR = 1.5            # Standard stops
MAX_OPEN_TRADES = 2            # Two positions

# Aggressive (experienced only)
RISK_PER_TRADE = 0.02          # 2%
STOP_LOSS_ATR = 1.0            # Tight stops
MAX_OPEN_TRADES = 3            # Multiple positions
```

### Performance Optimization

1. **Adjust Risk Based on Confidence**
   - Bot automatically reduces risk for lower confidence signals
   - Signals with <70% confidence get 70% normal size

2. **Use Cooldown After Losses**
   - Default: Stop after 3 consecutive losses
   - Prevents revenge trading
   - Gives time to review strategy

3. **Monitor Spread**
   - Wide spreads reduce profitability
   - Check broker's typical XAUUSD spread
   - ECN brokers often have better spreads

---

## 📞 Support & Resources

### Documentation
- `README.md` - Full strategy documentation
- `QUICKSTART.md` - Quick setup guide
- `PROJECT_SUMMARY.md` - Project overview

### Example Scripts
- `example_mt5_live.py` - Live/paper trading
- `example_mt5_backtest.py` - Backtesting with MT5 data
- `run_bot.py` - Custom bot runner (create your own)

### Logs
- `logs/trading_bot_mt5.log` - Main bot log
- `results/` - Backtest results

### MT5 Resources
- MetaTrader 5 Help: Press F1 in MT5
- MQL5 Community: https://www.mql5.com
- MT5 Python Docs: https://www.mql5.com/en/docs/python_metatrader5

---

## 🎓 Next Steps

1. ✅ Verify MT5 connection
2. ✅ Run test backtest
3. ✅ Paper trade for 1 week
4. ✅ Review and optimize parameters
5. ✅ Paper trade for 1 month
6. ✅ Analyze all trades
7. ✅ Start live with small capital
8. ✅ Scale gradually

---

## ⚠️ Disclaimer

**IMPORTANT:**
- Trading involves substantial risk of loss
- Past performance doesn't guarantee future results
- This bot is provided as-is without warranties
- **Test thoroughly** before risking real money
- **Start small** and scale gradually
- **Monitor regularly** - automation doesn't mean "set and forget"
- Use only capital you can afford to lose

---

**Good luck with your MT5 trading! 📈🚀**
