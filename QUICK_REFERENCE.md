# Quick Reference Guide
## TrendFollowing EA

---

## 🚀 Quick Start

### Installation (30 seconds)
1. Copy `TrendFollowingEA.mq5` to `MT5/MQL5/Experts/`
2. Compile in MetaEditor (F7)
3. Drag onto XAUUSD M15 chart
4. Enable AutoTrading

### First Backtest (2 minutes)
1. Open Strategy Tester (Ctrl+R)
2. Select EA, XAUUSD, M15, 2022-2024
3. Execution: "Every tick based on real ticks"
4. Click Start

---

## 📊 Trading Rules Summary

### H1 Trend Bias (Must Be True)

**Bullish:**
- Price > 55 EMA
- 8 EMA > 21 EMA > 34 EMA > 55 EMA

**Bearish:**
- Price < 55 EMA
- 8 EMA < 21 EMA < 34 EMA < 55 EMA

### M15 Entry Signals (ALL Must Be True)

**Buy Entry:**
1. Price closes above 21 EMA + (8 > 21 > 34)
2. MACD histogram > 0 AND accelerating
3. RSI crosses above 50

**Sell Entry:**
1. Price closes below 21 EMA + (8 < 21 < 34)
2. MACD histogram < 0 AND accelerating
3. RSI crosses below 50

### Exit Strategy

**Initial Stop Loss:**
- Buy: Entry - (2 × ATR)
- Sell: Entry + (2 × ATR)

**Trailing Stop:**
- Activates at 1× ATR profit
- Trails at 1× ATR distance
- Tightens to 0.5× ATR at 3× ATR profit (optional)

---

## ⚙️ Key Parameters

### Essential Settings

```
Risk_Per_Trade = 0.5          // Start conservative
ATR_Multiplier_ISL = 2.0      // Initial stop loss
ATR_Multiplier_Trail = 1.0    // Trailing distance
Max_Drawdown_Percent = 10.0   // Circuit breaker
```

### Optimization Targets

**Primary:**
- MA_Period_1 (6-10)
- MA_Period_2 (18-24)
- MA_Period_4 (50-60)
- ATR_Multiplier_ISL (1.5-2.5)
- ATR_Multiplier_Trail (0.8-1.5)

**Secondary:**
- ATR_Aggressive_Threshold (2.5-3.5)
- ATR_Aggressive_Multiplier (0.4-0.7)
- Risk_Per_Trade (0.5-1.0)

---

## 📈 Performance Targets

### Acceptable Results

```
Profit Factor:    > 1.5
Sharpe Ratio:     > 1.0
Win Rate:         45-60%
Max Drawdown:     < 15%
Total Trades:     > 50
Recovery Factor:  > 2.0
```

### Warning Signs

```
Profit Factor:    < 1.2
Win Rate:         < 35%
Max Drawdown:     > 20%
Total Trades:     < 30
Consecutive Loss: > 10
```

---

## 🔧 Common Issues & Fixes

### EA Not Trading

**Check:**
1. ✅ AutoTrading enabled (green button)
2. ✅ Smiley face in chart corner
3. ✅ No errors in Experts tab
4. ✅ H1 trend bias exists
5. ✅ No open position already
6. ✅ Circuit breaker not triggered

**Fix:**
```
- Restart MT5
- Re-compile EA (F7 in MetaEditor)
- Check Experts log for errors
- Verify symbol name (XAUUSD vs GOLD)
```

### Poor Backtest Results

**Investigate:**
1. Data quality (check History Center)
2. Spread settings (realistic?)
3. Market conditions (trending vs ranging)
4. Parameter optimization needed
5. Too few trades (< 50)

**Fix:**
```
- Download more historical data
- Set realistic spread (0.20-0.30 for Gold)
- Run optimization
- Test different time periods
```

### Circuit Breaker Triggered

**Causes:**
- Drawdown exceeded 10%
- Market conditions changed
- Poor parameter fit

**Actions:**
```
1. Stop EA immediately
2. Review recent trades
3. Check if market shifted (trending → ranging)
4. Re-optimize parameters
5. Reduce risk per trade
6. Demo test before re-starting
```

---

## 🎯 Risk Management

### Account Size Guidelines

**< $5,000:**
```
Risk_Per_Trade = 0.5%
Max_Drawdown_Percent = 8%
Enable_Circuit_Breaker = true
```

**$5,000 - $25,000:**
```
Risk_Per_Trade = 0.75%
Max_Drawdown_Percent = 10%
Enable_Circuit_Breaker = true
```

**> $25,000:**
```
Risk_Per_Trade = 1.0%
Max_Drawdown_Percent = 12%
Enable_Circuit_breaker = true
```

### Position Size Examples

**$10,000 account, 0.5% risk:**
- Risk amount: $50
- ATR: 8.0
- Stop distance: 16.0 (2× ATR)
- Position size: ~0.03 lots (calculated automatically)

---

## 📋 Daily Checklist

### Morning (5 min)
- [ ] Verify EA running (smiley face visible)
- [ ] Check open positions
- [ ] Review overnight P&L
- [ ] Check for errors in log

### Evening (5 min)
- [ ] Review day's trades
- [ ] Check drawdown level
- [ ] Verify no unusual activity
- [ ] Plan for tomorrow

### Weekly (15 min)
- [ ] Calculate week's performance
- [ ] Review all closed trades
- [ ] Check if H1 trend still aligned
- [ ] Verify broker execution quality

### Monthly (30 min)
- [ ] Full performance analysis
- [ ] Compare to backtest results
- [ ] Check parameter validity
- [ ] Consider re-optimization if needed
- [ ] Review risk management

---

## 🔍 Log File Analysis

### What to Look For

**Healthy Operation:**
```
[Timestamp] TrendFollowing EA initialized successfully
[Timestamp] === BUY SIGNAL ===
[Timestamp] Entry: 2045.50 | SL: 2029.50 | Lot: 0.03
[Timestamp] BUY order executed successfully. Ticket: 123456
[Timestamp] Trailing stop updated for ticket: 123456
[Timestamp] New SL: 2053.20 | Profit in ATR: 2.15
```

**Problems to Investigate:**
```
[Timestamp] ERROR: Invalid ATR value
[Timestamp] ERROR: Buy order failed. Code: 10015
[Timestamp] !!! CIRCUIT BREAKER TRIGGERED !!!
[Timestamp] ERROR: Failed to create indicator handles!
```

### Error Code Reference

```
10004: Requote (slippage too high)
10006: Request rejected (broker issue)
10013: Invalid request (parameter error)
10015: Invalid price (market closed or bad quote)
10016: Invalid stops (SL/TP too close)
10019: Not enough money
```

---

## 📊 Optimization Quick Guide

### 5-Minute Optimization

**For rapid testing:**
```
1. Strategy Tester → Optimization: ON
2. Select parameters: MA_Period_1, MA_Period_2, ATR_Multiplier_ISL
3. Ranges: MA1(6-10), MA2(18-24), ATR(1.5-2.5)
4. Target: Profit Factor
5. Algorithm: Genetic (fast)
6. Start
```

### Full Optimization (Recommended)

**For serious deployment:**
```
1. Data: 3 years minimum
2. Reserve: 30% for forward testing
3. Parameters: 5 max (MA1, MA2, MA4, ATR_ISL, ATR_Trail)
4. Target: Sharpe Ratio or Complex criterion
5. Algorithm: Slow Complete (for < 10,000 runs)
6. Validate: Forward test must match 60-120% of backtest
```

---

## 🎓 Best Practices

### Before Going Live
1. ✅ Backtest 3+ years
2. ✅ Forward test passed
3. ✅ Demo test 1+ month
4. ✅ Start with 0.5% risk
5. ✅ Document parameters
6. ✅ Verify broker quality

### While Trading
1. ✅ Monitor daily
2. ✅ Never override EA manually (let it run)
3. ✅ Track actual vs expected performance
4. ✅ Keep VPS/computer running 24/7
5. ✅ Log all interventions

### If Performance Degrades
1. ⚠️ Stop EA immediately
2. ⚠️ Analyze recent trades
3. ⚠️ Check market conditions
4. ⚠️ Re-optimize on recent data
5. ⚠️ Demo test new parameters
6. ⚠️ Restart with reduced risk

---

## 🚨 Emergency Actions

### Circuit Breaker Triggered
```
1. DO NOT restart EA immediately
2. Analyze why drawdown occurred
3. Check if market changed fundamentally
4. Re-optimize on recent data
5. Demo test for 2+ weeks
6. Restart with 50% risk
```

### Broker Issues (Slippage/Requotes)
```
1. Document evidence (screenshots)
2. Contact broker support
3. Consider switching brokers
4. Test execution quality on demo
5. Adjust Slippage parameter if needed
```

### Unexpected Losses
```
1. Verify EA logic (read code)
2. Check for news events (economic calendar)
3. Review all parameters
4. Ensure spreads were realistic in backtest
5. Compare live vs backtest execution
```

---

## 📞 Support Resources

### Documentation
- README.md - Full guide
- OPTIMIZATION_GUIDE.md - Backtesting details
- QUICK_REFERENCE.md - This file

### Code Files
- TrendFollowingEA.mq5 - Main EA (editable)

### Logs
- MT5 Experts tab - Real-time log
- MT5 Journal tab - System messages
- Strategy Tester Report - Backtest results

### Community
- MQL5.com - MQL5 programming
- TradingView - Chart analysis
- MyFXBook - Performance tracking

---

## 🎯 Success Metrics

### Week 1
- EA running without errors
- 1-3 trades executed
- Drawdown < 5%

### Month 1
- 10-20 total trades
- Profit Factor > 1.3
- Performance similar to demo test

### Month 3
- 30-60 total trades
- Clear trend: profitable or not
- Decide: continue or re-optimize

### Month 6+
- Statistical significance achieved
- Compare to backtest (should be 70-130%)
- Consider scaling up if successful

---

## ✅ Pre-Flight Checklist

Before enabling AutoTrading:

- [ ] EA compiled without errors
- [ ] Correct symbol (XAUUSD)
- [ ] Correct timeframe (M15)
- [ ] Parameters configured
- [ ] Risk per trade ≤ 0.5% (first time)
- [ ] Circuit breaker enabled
- [ ] AutoTrading button clicked
- [ ] Smiley face visible on chart
- [ ] No errors in Experts log
- [ ] VPS/computer stable connection

**Ready to trade! 🚀**

---

*Keep this guide handy for quick reference during trading operations.*
