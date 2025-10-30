# ICT XAUUSD Hybrid EA - Installation & Usage Guide

## 📋 Overview

This Expert Advisor implements **ICT Smart Money Concepts** for automated XAUUSD trading on MetaTrader 5. It combines:
- Market Structure analysis (MSS/CHOCH)
- Liquidity sweep detection
- Order Blocks, Fair Value Gaps, and Optimal Trade Entry zones
- Quantitative filters (ATR, Volume, Confidence Score)
- Session-based trading (Asia & London only)
- Advanced risk management

---

## 🚀 Installation

### Step 1: Copy EA to MetaTrader 5
1. Open your MetaTrader 5 data folder: `File → Open Data Folder`
2. Navigate to `MQL5/Experts/`
3. Copy `ICT_XAUUSD_Hybrid_EA.mq5` into this folder
4. Restart MetaTrader 5 or refresh the Navigator window

### Step 2: Compile the EA
1. In MT5, press `F4` to open MetaEditor
2. Open `ICT_XAUUSD_Hybrid_EA.mq5`
3. Press `F7` to compile
4. Verify there are no errors

### Step 3: Attach to XAUUSD Chart
1. Open XAUUSD chart (recommended: M5 timeframe)
2. Drag `ICT_XAUUSD_Hybrid_EA` from Navigator onto the chart
3. Enable "Allow Algo Trading" in the EA settings dialog
4. Click OK

---

## ⚙️ Configuration

### Risk Management Settings
```
Risk % per trade:           1.0%      (Conservative: 0.5%, Aggressive: 2.0%)
Max daily drawdown:         3.0%      (Circuit breaker activates)
Max trades per session:     2         (Prevents overtrading)
Take Profit RR:             1.5       (1.5:1 risk-reward ratio)
Use Partial TP:             false     (Close 50% at 1:1)
Use Break-even:             true      (Move SL to entry at 1R)
```

### Session Settings (GMT Timezone)
```
Asia Start Hour:            23        (11:00 PM GMT)
Asia End Hour:              6         (06:00 AM GMT)
London Start Hour:          7         (07:00 AM GMT)
London End Hour:            11        (11:00 AM GMT)
```

**Important:** Adjust session times to match your broker's server time offset from GMT.

### ICT Settings
```
Swing Lookback:             20        (Bars for structure detection)
Min OB Body Size:           50        (Points - filters small order blocks)
OTE Fib Low:                0.62      (Lower bound of OTE zone)
OTE Fib High:               0.79      (Upper bound of OTE zone)
SL Buffer Points:           10        (Buffer beyond zone for stop loss)
```

### Quantitative Filters
```
ATR Period:                 14        (Standard ATR calculation)
ATR Min Multiplier:         0.6       (Min volatility threshold)
ATR Max Multiplier:         2.0       (Max volatility threshold)
Volume Lookback:            20        (Bars for volume average)
Volume Multiplier:          1.0       (Volume must exceed mean)
Confidence Threshold:       0.7       (Min score to execute trade)
Max Spread Points:          2000      (Skip if spread too wide)
```

### Visualization
```
Show Levels:                true      (Previous session high/low/mid)
Show Zones:                 true      (OB/FVG/OTE zones)
Show Labels:                true      (Entry/exit arrows)
```

### Safety
```
Enable Circuit Breaker:     true      (Auto-stop at max DD)
No Trade Friday:            true      (Stop trading Fri > 20:00)
Magic Number:               123456    (Unique EA identifier)
```

---

## 📊 How It Works

### 1. Session Detection
- EA tracks Asia (23:00-06:00) and London (07:00-11:00) sessions
- Previous session high/low become liquidity targets
- Only trades during active sessions

### 2. Liquidity Sweep Detection
**Buy Setup:**
- Price wicks below previous session low
- Closes back inside range
- Indicates sell-side liquidity grab

**Sell Setup:**
- Price wicks above previous session high
- Closes back inside range
- Indicates buy-side liquidity grab

### 3. Market Structure Confirmation
- **Bullish MSS:** Higher highs + higher lows
- **Bearish MSS:** Lower highs + lower lows
- Structure must align with sweep direction

### 4. Entry Zone Identification
EA looks for confluence of:
- **Order Blocks:** Last opposite candle before impulse
- **Fair Value Gaps:** 3-candle displacement gaps
- **OTE Zones:** 0.62-0.79 Fibonacci retracement

### 5. Quantitative Validation
Each setup gets a confidence score (0-1.0):

| Component | Weight |
|-----------|--------|
| Liquidity sweep | 0.25 |
| MSS/CHOCH | 0.20 |
| OB/FVG confluence | 0.25 |
| OTE alignment | 0.10 |
| Volume & ATR valid | 0.10 |
| HTF bias | 0.10 |

**Trade executes only if score ≥ 0.7**

### 6. Trade Execution

**Long Entry:**
1. Sweep below previous low ✓
2. Bullish MSS confirmed ✓
3. Price retraces to OB/FVG/OTE ✓
4. Entry: Market buy
5. SL: Below OB low - buffer
6. TP: 1.5× risk distance

**Short Entry:**
1. Sweep above previous high ✓
2. Bearish MSS confirmed ✓
3. Price retraces to OB/FVG/OTE ✓
4. Entry: Market sell
5. SL: Above OB high + buffer
6. TP: 1.5× risk distance

### 7. Risk Management
- **Dynamic lot sizing** based on SL distance and risk %
- **Circuit breaker** stops trading at 3% daily drawdown
- **Max 2 trades per session** prevents overtrading
- **Break-even move** at 1R profit (optional)
- **Partial TP** at 1:1 (optional)

---

## 📈 Visual Indicators

When EA is running, you'll see:

**Lines:**
- 🔴 Red dashed line: Previous session high (sell-side liquidity)
- 🟢 Green dashed line: Previous session low (buy-side liquidity)
- 🟡 Yellow dotted line: Session midpoint

**Zones:**
- 🟢 Green boxes: Bullish zones (OB/FVG/OTE)
- 🔴 Red boxes: Bearish zones (OB/FVG/OTE)

**Arrows:**
- 🟢 Green up arrow: Long entry
- 🔴 Red down arrow: Short entry

---

## 🧪 Backtesting

### Recommended Settings
1. **Data:** Use quality tick data (≥1 year)
2. **Timeframe:** M5 chart
3. **Spread:** Set realistic spread (10-20 points typical for XAUUSD)
4. **Execution:** Every tick based on real ticks
5. **Initial deposit:** $10,000+ recommended

### Key Metrics to Monitor
- Win rate (target: >45%)
- Average Risk:Reward (target: >1.3)
- Profit factor (target: >1.5)
- Max drawdown (target: <10%)
- Expectancy per trade

### Optimization Parameters
Focus on optimizing:
1. **Confidence Threshold** (0.6-0.8)
2. **ATR Multipliers** (0.5-2.5)
3. **Swing Lookback** (15-30)
4. **Session Times** (match broker timezone)

**Warning:** Avoid over-optimization. Test on out-of-sample data.

---

## ⚠️ Important Notes

### Broker Requirements
- ✅ MT5 platform
- ✅ Hedging or netting account
- ✅ Low spread on XAUUSD (<30 points)
- ✅ Fast execution (<100ms)
- ✅ Algo trading allowed

### Timezone Configuration
**Critical:** Ensure session times match your broker's server timezone.

Example adjustments:
- Broker is GMT+2: Subtract 2 hours from inputs
- Broker is GMT-5: Add 5 hours to inputs

Use the "Market Watch" window to verify current server time.

### Symbol Name Variations
EA supports common XAUUSD variants:
- XAUUSD
- XAUUSD.pro
- XAUUSDm
- Any symbol containing "XAU"

If your broker uses a different name, modify the symbol check in `OnInit()`.

---

## 🔧 Troubleshooting

### EA Not Trading
1. **Check session times** - Verify GMT offset matches broker
2. **Check spread** - Must be <2000 points
3. **Check circuit breaker** - May be triggered from previous losses
4. **Check logs** - Look for error messages in "Experts" tab

### Compilation Errors
1. Ensure you're using MT5 (not MT4)
2. Update MetaTrader to latest version
3. Check that Trade library is available

### Positions Not Opening
1. **Account permissions** - Enable algo trading in settings
2. **Margin** - Ensure sufficient free margin
3. **Confidence score** - May be below threshold (check logs)
4. **Max trades** - May have hit session limit

### Unexpected Behavior
1. **Review logs** - All trades logged with reasoning
2. **Check visualization** - Verify zones are drawing correctly
3. **Monitor confidence scores** - Printed for each potential trade

---

## 📊 Performance Expectations

### Realistic Targets (Based on ICT Concepts)
- **Win Rate:** 40-55%
- **Average RR:** 1.5-2.0
- **Monthly Return:** 5-15% (with 1% risk)
- **Max Drawdown:** 10-20%
- **Trades per Week:** 2-8

### High Performance Profile
- Confidence threshold: 0.75+
- Tight ATR filter: 0.7-1.8
- Conservative RR: 2.0+
- Result: Lower frequency, higher quality

### Balanced Profile (Default)
- Confidence threshold: 0.70
- Standard ATR filter: 0.6-2.0
- Moderate RR: 1.5
- Result: Moderate frequency, good quality

---

## 🛡️ Safety Features

### Automatic Protection
- ✅ Daily drawdown circuit breaker (3%)
- ✅ Spread monitoring (skips wide spreads)
- ✅ Volume validation (filters low conviction moves)
- ✅ ATR volatility range check
- ✅ Session restriction (no off-hours trading)
- ✅ Friday trading cutoff (20:00 GMT)
- ✅ One trade per signal lock

### Manual Overrides
- Can disable circuit breaker (not recommended)
- Can adjust risk % dynamically
- Can modify session times
- Can disable visualization for performance

---

## 📝 Logging

EA logs all important events:
- Session start/end
- Liquidity sweep detection
- MSS/CHOCH signals
- Trade execution with reasoning
- Circuit breaker activation
- Daily P/L and balance updates

**View logs:** MT5 → Toolbox → Experts tab

---

## 🔄 Updates & Maintenance

### Version History
- **v1.00** - Initial release with full ICT framework

### Planned Enhancements
- DXY/US10Y correlation filter
- Kelly criterion position sizing
- Machine learning volatility regime classifier
- Advanced order flow analysis
- Multi-timeframe structure analysis

---

## 📚 Additional Resources

### ICT Concepts
- Market Structure Shifts (MSS)
- Change of Character (CHOCH)
- Order Blocks (OB)
- Fair Value Gaps (FVG)
- Optimal Trade Entry (OTE)
- Liquidity Engineering

### Recommended Learning
1. Study ICT's free YouTube content
2. Practice identifying setups manually
3. Backtest with strategy tester
4. Forward test on demo account (≥3 months)
5. Start with minimum risk % on live

---

## ⚖️ Disclaimer

This EA is provided for educational purposes. Past performance does not guarantee future results. Trading XAUUSD involves substantial risk of loss. Only trade with capital you can afford to lose. Test thoroughly on demo accounts before live trading.

**Use at your own risk.**

---

## 📞 Support

For issues or questions:
1. Check troubleshooting section
2. Review MT5 Expert logs
3. Verify all settings match your broker environment
4. Test on demo account first

---

## ✅ Pre-Flight Checklist

Before going live:
- [ ] Tested on demo for ≥1 month
- [ ] Session times verified with broker timezone
- [ ] Risk % set conservatively (≤1%)
- [ ] Circuit breaker enabled
- [ ] Spread verified as reasonable
- [ ] Account has sufficient margin
- [ ] Algo trading enabled in MT5
- [ ] Logs reviewed for errors
- [ ] Visualization confirmed working
- [ ] Backup plan for internet/power failure

---

**Happy Trading! 📈**
