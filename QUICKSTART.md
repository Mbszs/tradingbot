# Quick Start Guide

Get started with the ICT XAUUSD Trading Bot in 5 minutes!

## 🚀 Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Verify Installation

```bash
python test_installation.py
```

This will check that all components are properly installed.

## 🎯 First Run (Demo Mode)

Run the bot with sample data to test functionality:

```bash
python example_usage.py
```

Select option `1` to run with sample data.

You should see:
- Market analysis output
- ICT concept detection (OBs, FVGs, liquidity sweeps)
- Trade signals (if conditions are met)
- Trading statistics

## ⚙️ Configuration

### Edit `config.py`

**Risk Settings** (adjust these first):

```python
RISK_CONFIG = {
    'account_balance': 10000,        # Your account size
    'risk_per_trade_pct': 1.0,       # 1% risk per trade
    'max_daily_drawdown_pct': 3.0,   # 3% max daily loss
}
```

**Session Settings**:

```python
SESSIONS = {
    'ASIA': {'start': '23:00', 'end': '06:00', 'enabled': True},
    'LONDON': {'start': '07:00', 'end': '11:00', 'enabled': True},
}
```

**ICT Parameters** (fine-tune based on backtesting):

```python
ICT_CONFIG = {
    'liquidity_tolerance_pips': 2,   # Tolerance for equal highs/lows
    'fvg_min_gap_pips': 5,          # Minimum FVG size
    'fib_ote_min': 0.618,           # OTE zone start
    'fib_ote_max': 0.79             # OTE zone end
}
```

## 📊 Connecting to Your Broker

### Option 1: MetaTrader 5

1. **Install MT5 Python package**:
   ```bash
   pip install MetaTrader5
   ```

2. **Configure in `config.py`**:
   ```python
   BROKER_CONFIG = {
       'broker_type': 'MT5',
       'server': 'YourBrokerServer-Demo',  # or Live
       'live_trading': False  # True for live
   }
   ```

3. **Update `example_usage.py`**:
   - Uncomment the MT5 sections
   - Add your login credentials
   - Run: `python example_usage.py` and select option `2`

### Option 2: Yahoo Finance (Backtest Only)

1. **Install yfinance**:
   ```bash
   pip install yfinance
   ```

2. **Use built-in data fetcher**:
   ```python
   from data_fetcher import DataFetcher
   
   fetcher = DataFetcher(source='yahoo')
   df = fetcher.fetch_ohlc('XAUUSD', '1h', 500)
   ```

### Option 3: CSV Files

1. **Prepare CSV files** in `data/` folder:
   - Format: `XAUUSD_1h.csv`
   - Columns: `timestamp,open,high,low,close,volume`

2. **Use CSV data fetcher**:
   ```python
   fetcher = DataFetcher(source='csv')
   df = fetcher.fetch_ohlc('XAUUSD', '1h', 500)
   ```

## 📈 Understanding the Output

### Market Analysis

```
Market Analysis Complete:
  HTF Bias: bullish          # Higher timeframe trend
  Current Bias: bullish      # Current timeframe trend
  Bias Aligned: True         # Trends aligned? ✅
  Active OBs: 3              # Unmitigated order blocks
  Active FVGs: 2             # Unfilled fair value gaps
```

### Entry Conditions Check

The bot checks 7+ confluence factors:

1. ✅ **Liquidity Sweep** - Stop run detected
2. ✅ **Structure Shift** - MSS/CHOCH confirmed
3. ✅ **OB or FVG** - Price in valid entry zone
4. ✅ **OTE Zone** - In 61.8-79% retracement
5. ✅ **Volume Spike** - Above average volume
6. ✅ **ATR Valid** - Volatility in normal range
7. ✅ **Trend Aligned** - Momentum confirmed

### Trade Execution

```
✅ Trade opened: XAUUSD_20240115_083005
   Entry: 2045.50
   Stop Loss: 2040.00 (55 pips)
   Take Profit: 2056.00 (105 pips)
   Position Size: 0.18 lots
   Risk: $100.00 (1.0%)
```

## 🧪 Testing Workflow

### Phase 1: Backtest (1-2 weeks)
- Use historical data (Yahoo Finance or MT5 demo)
- Run on past 1-2 years of data
- Analyze win rate, profit factor, drawdown
- Adjust parameters in `config.py`

### Phase 2: Paper Trade (2-4 weeks)
- Connect to broker demo account
- Run bot in real-time with demo money
- Monitor for 2-4 weeks
- Verify signals match your expectations

### Phase 3: Live Small (1-2 weeks)
- Set `live_trading: True` in config
- Use MINIMUM position sizes (0.01 lots)
- Risk only 0.25-0.5% per trade initially
- Monitor closely

### Phase 4: Full Live
- Gradually increase position size
- Never exceed 1% risk per trade
- Keep detailed logs
- Review performance weekly

## 🔍 Common Issues

### "No trades being executed"

**Reasons**:
- Not in trading session (Asia/London only)
- Bias not aligned between timeframes
- No recent liquidity sweep detected
- Insufficient confluences

**Solution**: Check logs for specific rejection reason.

### "Position size too small"

**Solution**: Increase `account_balance` in config or widen stop loss.

### "ATR filter failing"

**Solution**: Adjust `atr_min_multiplier` and `atr_max_multiplier` in config.

## 📚 Learning Resources

### ICT Concepts
1. Watch ICT's YouTube channel (start with 2022 mentorship)
2. Understand: Order Blocks, FVGs, Liquidity Sweeps, MSS/CHOCH
3. Practice identifying these on charts manually first

### System Customization
- `market_structure.py` - Modify swing detection
- `liquidity.py` - Adjust liquidity tolerance
- `quant_filters.py` - Add your own filters
- `risk_management.py` - Customize trade management

## ⚠️ Important Reminders

1. **Never skip testing phases** - Rushing leads to losses
2. **Start small** - You can always increase size later
3. **Keep logs** - Essential for improvement
4. **Review trades** - Learn from both wins and losses
5. **Stay disciplined** - Don't override the system manually

## 🎓 Next Steps

1. ✅ Complete installation test
2. ✅ Run with sample data
3. ✅ Study the output and understand each component
4. ✅ Backtest with historical data
5. ✅ Paper trade on demo account
6. ✅ Start live with minimum size
7. ✅ Scale gradually

## 💬 Support

- Read `README.md` for detailed documentation
- Check code comments for implementation details
- Test thoroughly before live trading
- Document any modifications you make

---

**Good luck, and trade smart! 📈**

*Remember: The best traders are patient, disciplined, and always learning.*
