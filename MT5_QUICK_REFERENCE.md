# MT5 Quick Reference Card

One-page reference for common tasks and commands.

---

## 🚀 Quick Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Test MT5 connection
python example_mt5_live.py  # Choose option 2
```

### Backtesting
```bash
# Full backtest with optimization
python example_mt5_backtest.py

# Quick backtest (3 months)
python example_mt5_backtest.py  # Choose option 2
```

### Trading
```bash
# Paper trading (safe)
python example_mt5_live.py  # Choose paper mode

# Live trading (after testing!)
python example_mt5_live.py  # Choose live mode
```

---

## 📊 Key Files

| File | Purpose |
|------|---------|
| `config.py` | All strategy settings |
| `mt5_connector.py` | MT5 connection & trading |
| `trading_bot_mt5.py` | Main bot for MT5 |
| `example_mt5_live.py` | Run live/paper trading |
| `example_mt5_backtest.py` | Backtest with MT5 data |
| `MT5_SETUP_GUIDE.md` | Complete setup guide |

---

## ⚙️ Essential Config Settings

```python
# config.py

# Symbol (adjust for your broker)
SYMBOL = "XAUUSD"  # or "GOLD", "XAU/USD"

# Risk (start conservative!)
RISK_PER_TRADE = 0.01          # 1% per trade
MAX_OPEN_TRADES = 2            # Max positions

# Stops & Targets
STOP_LOSS_ATR = 1.5            # Stop distance
TAKE_PROFIT_1 = 1.5            # First target (33%)
TAKE_PROFIT_2 = 2.5            # Second target (33%)

# Timeframes
TIMEFRAME_ENTRY = "1h"         # Entry signals
TIMEFRAME_HTF = "1d"           # Trend bias
```

---

## 🔧 Common Code Snippets

### Connect to MT5
```python
from mt5_connector import MT5Connector

mt5 = MT5Connector(symbol="XAUUSD", magic_number=234000)
if mt5.connect():
    print("Connected!")
else:
    print("Failed")
```

### Get Account Info
```python
account = mt5.get_account_info()
print(f"Balance: ${account['balance']:,.2f}")
print(f"Equity: ${account['equity']:,.2f}")
```

### Get Current Price
```python
price = mt5.get_current_price()
print(f"Bid: {price['bid']}")
print(f"Ask: {price['ask']}")
```

### Get Historical Data
```python
# Get 1H data (last 500 bars)
df = mt5.get_historical_data('1h', bars=500)
print(df.tail())
```

### Open Position (Manual)
```python
ticket = mt5.open_position(
    position_type='long',      # 'long' or 'short'
    volume=0.01,               # Lot size
    stop_loss=1950.00,         # SL price
    take_profit=1980.00,       # TP price
    comment="Manual trade"
)
```

### Close Position
```python
success = mt5.close_position(ticket=12345678)
```

### Get Open Positions
```python
positions = mt5.get_open_positions()
for pos in positions:
    print(f"Ticket: {pos['ticket']}")
    print(f"Type: {pos['type']}")
    print(f"Volume: {pos['volume']}")
    print(f"Profit: ${pos['profit']:.2f}")
```

---

## 🎯 Strategy Entry Conditions

**LONG Entry Requires:**
- ✅ Daily trend bullish (price > EMA 50/200)
- ✅ Market structure bullish
- ✅ Price at FVG or Order Block
- ✅ MACD bullish
- ✅ RSI > 50
- ✅ Volume confirmation
- ✅ Within 2 ATR of 50 EMA

**SHORT Entry Requires:**
- Same but inverted

---

## 🛠️ Troubleshooting Quick Fixes

| Problem | Solution |
|---------|----------|
| Can't connect | Ensure MT5 running & logged in |
| Symbol not found | Add XAUUSD to Market Watch |
| No data | Open XAUUSD chart, scroll back |
| Trade failed | Check margin & minimum lot size |
| Bot stops | Check logs/trading_bot_mt5.log |

---

## 📈 Performance Targets

| Metric | Target |
|--------|--------|
| Win Rate | 55-65% |
| Profit Factor | 1.5-2.5+ |
| Max Drawdown | <15% |
| Avg R:R | 2.0-3.0 |
| Sharpe Ratio | >1.5 |

---

## 🔍 Monitoring Commands

### Watch Logs
```bash
# Real-time log monitoring
tail -f logs/trading_bot_mt5.log

# Linux/Mac: Watch with updates
watch -n 10 tail -20 logs/trading_bot_mt5.log
```

### Check Running Bot
```bash
# Linux/Mac
ps aux | grep python | grep bot

# Windows
tasklist | findstr python
```

---

## 💾 Backup Important Files

Before live trading, backup:
- [ ] `config.py` (your settings)
- [ ] `logs/` folder (trading history)
- [ ] `results/` folder (backtest results)

---

## 🔐 Security Checklist

- [ ] Never share MT5 credentials
- [ ] Use strong password
- [ ] Start with demo account
- [ ] Test thoroughly (1+ month)
- [ ] Set risk limits
- [ ] Monitor regularly
- [ ] Use VPS for 24/7 operation

---

## 📞 Getting Help

1. Check `MT5_SETUP_GUIDE.md` for detailed instructions
2. Review `README.md` for strategy details
3. Look at example scripts for usage patterns
4. Check logs for error messages

---

## 🎓 Recommended Testing Flow

```
1. Test Connection          → 5 minutes
2. Run Quick Backtest       → 10 minutes
3. Review Results           → 15 minutes
4. Adjust Config            → 10 minutes
5. Full Backtest           → 30 minutes
6. Paper Trade 1 Week      → Test bot behavior
7. Paper Trade 1 Month     → Verify consistency
8. Live with Small Capital → Start conservative
9. Monitor & Scale         → Increase gradually
```

---

## ⚡ Common Adjustments

### More Conservative
```python
RISK_PER_TRADE = 0.005         # 0.5%
STOP_LOSS_ATR = 2.0            # Wider
FVG_MIN_SIZE = 0.5             # Larger FVGs
```

### More Aggressive
```python
RISK_PER_TRADE = 0.02          # 2%
STOP_LOSS_ATR = 1.0            # Tighter
FVG_MIN_SIZE = 0.2             # Smaller FVGs
```

### More Trades
```python
MAX_DISTANCE_FROM_MA = 3.0     # Allow further entries
ENABLE_SESSION_FILTER = False  # Trade all sessions
```

### Higher Quality
```python
FVG_MIN_SIZE = 0.5             # Only large FVGs
MACD_HISTOGRAM_EXPANSION = True
RSI_LONG_THRESHOLD = 55        # Stronger momentum
```

---

**Print this page for quick reference while trading! 📄**
