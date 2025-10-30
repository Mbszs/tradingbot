# Trend Following EA - Gold/XAUUSD Trading Bot

**A professional, quantitative trend-following Expert Advisor for MetaTrader 5**

## 🎯 Strategy Overview

This EA implements an aggressive trend-following strategy designed for Gold (XAUUSD) trading. It combines multi-timeframe analysis with strict risk management to capture strong trending moves while protecting capital.

### Core Philosophy
- **Let profits run** (no fixed take profit)
- **Cut losses quickly** (volatility-based stop loss)
- **High-probability entries** (multiple confirmations required)
- **Strict risk control** (circuit breaker, position sizing)

---

## 📊 Trading Logic

### 1. H1 Trend Bias Filter (Primary)
The EA only trades in the direction of the H1 trend:

**Bullish Bias Requirements:**
- Price > 55-period EMA
- Perfect EMA alignment: 8 EMA > 21 EMA > 34 EMA > 55 EMA

**Bearish Bias Requirements:**
- Price < 55-period EMA
- Perfect EMA alignment: 8 EMA < 21 EMA < 34 EMA < 55 EMA

### 2. M15 Entry Signals (All Required)

Once H1 bias is established, the EA waits for **ALL THREE** confirmations on M15:

#### A) MA Ribbon Crossover & Alignment
- **Buy:** Price closes above 21 EMA AND 8 EMA > 21 EMA > 34 EMA
- **Sell:** Price closes below 21 EMA AND 8 EMA < 21 EMA < 34 EMA

#### B) MACD Confirmation
- **Buy:** MACD histogram > 0 AND accelerating (current > previous)
- **Sell:** MACD histogram < 0 AND accelerating (current < previous)

#### C) RSI Momentum
- **Buy:** RSI crosses above 50 from below
- **Sell:** RSI crosses below 50 from above

### 3. Risk Management

**Position Sizing:**
- Risk 0.5% - 1.0% of account balance per trade
- Dynamically calculated based on ATR stop loss distance

**Initial Stop Loss (ISL):**
- Buy: Entry - (2 × H1 ATR)
- Sell: Entry + (2 × H1 ATR)

**Trailing Stop (Dynamic Exit):**
- Activates after 1× ATR profit
- Trails at 1× ATR distance from current price
- **Aggressive mode:** Tightens to 0.5× ATR after 3× ATR profit

### 4. Safety Features

**Circuit Breaker:**
- Triggers at 10% drawdown from equity peak
- Automatically closes all positions
- Stops opening new trades

**Trade Management:**
- One position at a time (no hedging)
- No martingale or grid strategies
- Market execution only

---

## 🚀 Installation

### 1. MetaTrader 5 Setup
1. Copy `TrendFollowingEA.mq5` to your MT5 data folder:
   ```
   File → Open Data Folder → MQL5 → Experts
   ```

2. Compile the EA:
   - Open MetaEditor (F4 in MT5)
   - Open `TrendFollowingEA.mq5`
   - Click "Compile" (F7)
   - Ensure no errors in the log

3. Refresh Expert Advisors in MT5:
   - Right-click on "Expert Advisors" in Navigator
   - Select "Refresh"

### 2. Chart Setup
1. Open a chart for your symbol (recommended: XAUUSD/Gold)
2. Set chart timeframe to M15 (recommended for monitoring)
3. Drag the EA from Navigator onto the chart
4. Enable "AutoTrading" (top toolbar)

---

## ⚙️ Configuration

### Essential Parameters

#### H1 Trend Setup
```
MA_Period_1 = 8      // Fast EMA
MA_Period_2 = 21     // Medium EMA
MA_Period_3 = 34     // Slow EMA
MA_Period_4 = 55     // Trend Filter EMA
```

#### M15 Entry Setup
```
M15_MA_Period = 21                // Entry trigger EMA
Use_MACD_Confirmation = true      // Enable MACD filter
Use_RSI_Confirmation = true       // Enable RSI filter
RSI_Period = 14
RSI_Level = 50.0                  // Momentum threshold
```

#### Risk Management
```
Risk_Per_Trade = 0.5              // Risk 0.5% per trade
ATR_Period = 14
ATR_Multiplier_ISL = 2.0          // Initial stop: 2× ATR
ATR_Multiplier_Trail = 1.0        // Trailing stop: 1× ATR
ATR_Profit_Activation = 1.0       // Activate trail at 1× ATR profit
Use_Aggressive_Trail = true       // Tighten trail on large profits
ATR_Aggressive_Threshold = 3.0    // Trigger at 3× ATR profit
ATR_Aggressive_Multiplier = 0.5   // Tighten to 0.5× ATR
```

#### Circuit Breaker
```
Max_Drawdown_Percent = 10.0       // Shutdown at 10% drawdown
Enable_Circuit_Breaker = true     // Enable safety feature
```

### Recommended Settings for Different Account Sizes

**Conservative (< $5,000):**
- Risk_Per_Trade = 0.5%
- Enable_Circuit_Breaker = true
- Max_Drawdown_Percent = 8%

**Standard ($5,000 - $25,000):**
- Risk_Per_Trade = 0.75%
- Enable_Circuit_Breaker = true
- Max_Drawdown_Percent = 10%

**Aggressive (> $25,000):**
- Risk_Per_Trade = 1.0%
- Enable_Circuit_Breaker = true
- Max_Drawdown_Percent = 12%

---

## 📈 Backtesting Guide

### Strategy Tester Setup

1. **Open Strategy Tester** (Ctrl+R in MT5)

2. **Basic Settings:**
   - Expert Advisor: TrendFollowingEA
   - Symbol: XAUUSD (or GOLD depending on broker)
   - Period: M15
   - Date: Minimum 2-3 years of data recommended
   - Execution: Every tick based on real ticks
   - Initial Deposit: Match your live account

3. **Optimization Parameters:**
   
   **Primary optimization targets:**
   - MA_Period_1 (6 to 10, step 1)
   - MA_Period_2 (18 to 24, step 1)
   - MA_Period_4 (50 to 60, step 2)
   - ATR_Multiplier_ISL (1.5 to 2.5, step 0.25)
   - ATR_Multiplier_Trail (0.8 to 1.5, step 0.1)

   **Optimization goal:** 
   - Primary: Sharpe Ratio (risk-adjusted returns)
   - Secondary: Profit Factor > 1.5
   - Validate: Max Drawdown < 15%

4. **Forward Testing:**
   - Use 70% of data for optimization
   - Reserve 30% for forward testing
   - Results should be similar in both periods

### Key Metrics to Monitor

✅ **Good Performance Indicators:**
- Profit Factor > 1.5
- Win Rate > 45%
- Sharpe Ratio > 1.0
- Max Drawdown < 15%
- Recovery Factor > 2.0

⚠️ **Warning Signs:**
- Win Rate < 35% (too many false signals)
- Profit Factor < 1.2 (poor risk/reward)
- Max Drawdown > 20% (excessive risk)
- Large gap between backtest and forward test (overfitting)

---

## 🎓 Usage Best Practices

### Before Going Live

1. **Backtest thoroughly:**
   - Minimum 2 years of historical data
   - Test in different market conditions (trending, ranging, volatile)
   - Validate on out-of-sample data

2. **Demo test:**
   - Run on demo account for at least 1 month
   - Monitor during live market conditions
   - Verify execution quality with your broker

3. **Start small:**
   - Begin with minimum risk (0.5% or less)
   - Trade only 1-2 pairs initially
   - Gradually increase as confidence builds

### Ongoing Monitoring

**Daily:**
- Check for open positions and P&L
- Verify EA is running (check "Experts" log)
- Monitor circuit breaker status

**Weekly:**
- Review trade history and performance metrics
- Check if market conditions match strategy assumptions
- Verify correlation between H1 trend and M15 entries

**Monthly:**
- Full performance analysis
- Compare actual vs. backtested results
- Adjust parameters if needed (carefully!)

### When to Stop/Adjust

**Stop immediately if:**
- Circuit breaker triggers repeatedly
- Actual results significantly worse than backtest
- Broker execution quality deteriorates
- Major market structure changes (e.g., extreme volatility events)

**Consider adjustment if:**
- Win rate drops below 30% for extended period
- Average losing trade > 2× average winning trade
- Market enters prolonged ranging period (trend strategy struggles)

---

## ⚠️ Important Disclaimers

### Risk Warnings

1. **No guarantee of profits:** Past performance does not guarantee future results
2. **Market risk:** All trading involves risk of loss
3. **Broker dependency:** Execution quality affects results
4. **Optimization risk:** Over-optimized parameters may fail in live trading
5. **Technical risk:** Software bugs, connectivity issues, or platform errors may occur

### Strategy Limitations

- **Performs best in trending markets:** Struggles in ranging/choppy conditions
- **Slippage sensitive:** Requires good execution (tight spreads, fast fills)
- **News events:** Major economic releases can cause unexpected behavior
- **Drawdown periods:** Expect losing streaks (part of trend following)

### Broker Requirements

For optimal performance, ensure your broker provides:
- ✅ Tight spreads on XAUUSD (< 0.30 typically)
- ✅ Fast execution (< 100ms average)
- ✅ No slippage or minimal slippage
- ✅ Reliable VPS or low-latency connection
- ✅ Adequate historical data for backtesting

---

## 🔧 Troubleshooting

### EA Not Trading

**Check:**
1. AutoTrading enabled (button in toolbar should be green)
2. EA has smiley face icon in top-right of chart
3. No errors in "Experts" tab (Ctrl+T → Experts)
4. H1 trend bias exists (check EMAs manually)
5. M15 confirmations all present
6. Circuit breaker not triggered
7. No existing open position

### EA Crashing or Errors

**Common solutions:**
1. Re-compile the EA in MetaEditor
2. Restart MetaTrader 5
3. Check if indicator handles are valid (see Experts log)
4. Ensure sufficient historical data loaded (scroll chart back)
5. Verify symbol name matches exactly (XAUUSD vs GOLD)

### Poor Performance

**Investigate:**
1. Broker execution quality (check logs for rejections/requotes)
2. Market conditions (ranging vs. trending)
3. Parameter optimization needed for your specific broker/timeframe
4. Spread costs eating into profits
5. Slippage on entries/exits

---

## 📞 Support & Development

### Logging

The EA provides detailed logging in the "Experts" tab:
- Entry/exit signals with reasoning
- Position sizing calculations
- Trailing stop adjustments
- Circuit breaker status
- Error messages

Enable "Journal" and "Experts" tabs for full visibility.

### Customization

The code is well-commented and modular. Key functions:
- `GetH1TrendBias()` - Trend detection logic
- `CheckM15BuyEntry()` / `CheckM15SellEntry()` - Entry signals
- `CalculatePositionSize()` - Risk management
- `ManageOpenPositions()` - Trailing stop logic

Feel free to modify parameters or logic to suit your trading style.

---

## 📝 Version History

**v1.00** (2025-10-30)
- Initial release
- Multi-timeframe trend following
- ATR-based dynamic stops
- Circuit breaker protection
- Full MQL5 implementation

---

## 🎯 Next Steps

1. **Backtest** with your broker's data
2. **Optimize** parameters for your specific market
3. **Forward test** on demo account
4. **Monitor** performance for 1+ month
5. **Go live** with minimum risk
6. **Scale up** gradually as confidence builds

**Good luck and happy trading! 📈**

---

*Remember: Consistent profitability comes from discipline, risk management, and realistic expectations. This EA is a tool, not a magic solution.*
