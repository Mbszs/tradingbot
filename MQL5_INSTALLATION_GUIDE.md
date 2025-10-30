# MQL5 Expert Advisor - Installation Guide

## 📋 How to Install and Use the XAU/USD ICT Bot in MT5

---

## ✅ Step 1: Copy the Code (30 seconds)

1. **Open the EA file**
   - Open `XAU_USD_ICT_Bot.mq5` in a text editor
   - Press `Ctrl+A` to select all
   - Press `Ctrl+C` to copy

---

## 🔧 Step 2: Open MetaEditor (30 seconds)

1. **Open MT5 Terminal**
2. **Open MetaEditor**
   - Press `F4` in MT5
   - Or: Tools → MetaQuotes Language Editor

---

## 📝 Step 3: Create New Expert Advisor (1 minute)

1. **In MetaEditor:**
   - Click `File` → `New`
   - Select `Expert Advisor (template)`
   - Click `Next`

2. **Name your EA:**
   - Name: `XAU_USD_ICT_Bot`
   - Author: Your name (optional)
   - Click `Next`

3. **Skip parameters:**
   - Click `Next` (don't add parameters - we'll paste the full code)
   - Click `Finish`

4. **Clear default code:**
   - MetaEditor will open with template code
   - Press `Ctrl+A` (select all)
   - Press `Delete`

5. **Paste your code:**
   - Press `Ctrl+V` (paste the bot code)
   - Press `Ctrl+S` (save)

---

## 🔨 Step 4: Compile the EA (30 seconds)

1. **In MetaEditor:**
   - Press `F7` (or click the Compile button)
   - Wait for compilation

2. **Check for errors:**
   - Look at the bottom panel (Errors tab)
   - **Success:** "0 error(s), 0 warning(s)"
   - If errors: Take a screenshot and check code

**Expected output:**
```
Compiling 'XAU_USD_ICT_Bot.mq5'
0 error(s), 0 warning(s), compilation time: 250ms
```

---

## 📊 Step 5: Add EA to Chart (2 minutes)

### **Option A: Drag and Drop**

1. **In MT5 Terminal:**
   - Open `Navigator` (Ctrl+N)
   - Expand `Expert Advisors` folder
   - Find `XAU_USD_ICT_Bot`
   - **Drag it onto XAUUSD H1 chart**

### **Option B: Right-Click Method**

1. **Open XAUUSD chart:**
   - File → New Chart → XAUUSD
   - Change timeframe to H1 (1 hour)

2. **Attach EA:**
   - Right-click on chart
   - Template → Expert Advisors → XAU_USD_ICT_Bot

---

## ⚙️ Step 6: Configure Settings (2 minutes)

A settings window will appear. Here are the **recommended settings for beginners:**

### **Trading Settings**
```
Risk per trade (%): 0.5        ← Start conservative!
Maximum open trades: 1         ← One position at a time
Magic number: 234000           ← Keep default
```

### **Risk Management**
```
Stop loss (ATR): 2.0           ← Wider stops
Take profit 1: 1.5             ← First target
Take profit 2: 2.5             ← Second target
TP1 close percent: 33          ← Close 1/3 position
TP2 close percent: 33          ← Close another 1/3
Trailing activation: 2.0       ← Activate at 2R
Trailing ATR: 1.0              ← Trail with 1 ATR
```

### **Indicator Settings**
```
(Leave all defaults - they're optimized)
```

### **ICT Settings**
```
FVG minimum size: 0.3          ← Fair Value Gap size
OB lookback: 50                ← Order Block detection
```

### **Session Filters**
```
Enable session filter: true    ← Yes
Avoid Asian session: true      ← Yes (low liquidity)
```

### **Safety Settings**
```
Max consecutive losses: 3      ← Stop after 3 losses
Cooldown hours: 4              ← Wait 4 hours
Max daily loss: 3.0            ← 3% daily limit
```

### **Timeframes**
```
Higher timeframe: Daily        ← For trend bias
Structure timeframe: H4        ← For structure
```

**Click `OK`** when done!

---

## 🚀 Step 7: Enable Algo Trading (30 seconds)

**IMPORTANT:** The EA won't work without this!

1. **Check top toolbar:**
   - Look for "AutoTrading" button
   - Should be **GREEN** (enabled)
   - If red: Click it to enable

2. **Or in menu:**
   - Tools → Options → Expert Advisors
   - Check ✅ "Allow algorithmic trading"
   - Click OK

---

## ✅ Step 8: Verify EA is Running (30 seconds)

**You should see:**

1. **Smiley face in top-right corner:**
   - 😊 = EA is running
   - 🙁 = EA stopped or error

2. **Expert tab shows activity:**
   - Press `Ctrl+T` (open Terminal)
   - Go to `Experts` tab
   - You should see:
   ```
   ===================================
   XAU/USD ICT Trading Bot Started
   ===================================
   Risk per trade: 0.5%
   Magic Number: 234000
   ```

---

## 📱 What Happens Next?

### **The EA will:**
- ✅ Monitor XAU/USD every hour (H1 timeframe)
- ✅ Analyze market structure
- ✅ Detect Fair Value Gaps and Order Blocks
- ✅ Generate signals when all conditions align
- ✅ Open positions automatically
- ✅ Manage trades with partial profits
- ✅ Apply trailing stops

### **You'll see in Experts tab:**
```
Checking for signals...
LONG signal detected! Confidence: 75%
========================================
Position opened successfully!
Type: BUY
Price: 2050.45
SL: 2045.30
TP1: 2058.12
Lot: 0.01
========================================
```

---

## 🎯 Quick Settings Guide

### **Conservative (Recommended for Beginners)**
```
Risk: 0.5%
Max trades: 1
Stop loss ATR: 2.0
```

### **Moderate**
```
Risk: 1.0%
Max trades: 2
Stop loss ATR: 1.5
```

### **Aggressive (Experienced Only)**
```
Risk: 2.0%
Max trades: 3
Stop loss ATR: 1.0
```

---

## 🔧 Troubleshooting

### Issue: "Smiley face is sad 🙁"

**Solutions:**
1. Check algo trading is enabled (top toolbar - green)
2. Right-click chart → Expert Advisors → Properties → Check "Allow live trading"
3. Check account has sufficient margin

### Issue: "No trades after hours"

**This is normal!** The strategy is selective:
- Waits for perfect setups
- Expects 2-5 trades per week
- Quality over quantity

**Why no trades:**
- Market ranging (not trending)
- No ICT zones nearby
- Filters not aligned
- Wrong session

### Issue: "Error in Experts tab"

**Common errors:**
```
"Not enough money" → Reduce lot size or risk %
"Trade disabled" → Enable algo trading
"Invalid stops" → Spread too wide, try different broker
```

---

## 📊 Monitoring Your EA

### **View Open Positions:**
1. Press `Ctrl+T` (Terminal)
2. Go to `Trade` tab
3. See all open positions with SL/TP

### **View Trade History:**
1. In Terminal → `History` tab
2. Right-click → `Custom Period`
3. Select date range
4. View all closed trades

### **View Logs:**
1. In Terminal → `Experts` tab
2. See all EA activity
3. Right-click → `Open`
4. Saves to MT5/MQL5/Logs folder

---

## 💡 Tips for Success

### **1. Test on Demo First**
- Run on demo account for 1+ month
- Verify strategy works
- Get comfortable with settings

### **2. Don't Interfere**
- Let EA manage positions
- Don't manually close trades
- Don't modify SL/TP manually
- Trust the process

### **3. Monitor Daily**
- Check Experts tab for signals
- Review open positions
- Check for errors
- Keep trading journal

### **4. One Chart Only**
- Run EA on ONE XAUUSD H1 chart only
- Don't duplicate on multiple charts
- Will cause conflicting trades

### **5. VPS for 24/7**
- Use VPS if running 24/7
- Ensures EA never stops
- Better execution
- No local PC issues

---

## 🎓 Settings Explanation

### **What Each Setting Does:**

**Risk per trade (%):**
- % of account balance to risk
- 0.5% = Very conservative
- 1.0% = Moderate
- 2.0% = Aggressive

**Stop loss ATR:**
- Stop loss distance in ATR multiples
- 1.5 = Tighter stops (more trades stopped)
- 2.0 = Wider stops (safer)

**Take profit 1/2:**
- Profit targets in R (risk) multiples
- 1.5R = Take profit at 1.5x risk
- 2.5R = Take profit at 2.5x risk

**FVG minimum size:**
- Minimum Fair Value Gap size to trade
- 0.2 = More FVGs (more trades)
- 0.5 = Fewer FVGs (higher quality)

**Session filter:**
- Enable = Only trade during London/NY
- Disable = Trade 24/5

---

## 📋 Pre-Flight Checklist

Before going live:
- [ ] EA compiled successfully (0 errors)
- [ ] Attached to XAUUSD H1 chart
- [ ] Algo trading enabled (green button)
- [ ] Smiley face is happy 😊
- [ ] Settings configured (0.5% risk)
- [ ] Demo account selected
- [ ] Internet connection stable
- [ ] MT5 account has sufficient balance

---

## 🔄 Updating Settings

**To change settings after EA is running:**

1. **Remove EA from chart:**
   - Right-click chart
   - Expert Advisors → Remove

2. **Re-attach with new settings:**
   - Drag EA from Navigator
   - Change settings in dialog
   - Click OK

**Or:**
- Right-click chart
- Expert Advisors → Properties
- Go to Inputs tab
- Modify settings
- Click OK

---

## 💾 Backup Your EA

**Important:** Save a copy!

**EA location:**
```
C:\Users\YourName\AppData\Roaming\MetaQuotes\Terminal\[broker-id]\MQL5\Experts\
```

**Or in MetaEditor:**
- File → Open Data Folder
- Navigate to MQL5 → Experts
- Copy `XAU_USD_ICT_Bot.mq5`

---

## 📞 Need Help?

### **Check Experts Tab First:**
- Press Ctrl+T
- Go to Experts tab
- Read recent messages
- Look for errors

### **Common Messages:**

```
✅ "Position opened successfully" - Trade executed
⚠️ "Cannot trade: cooldown active" - Safety pause
⚠️ "Max daily loss reached" - Stop for today
ℹ️ "No signal detected" - Waiting for setup
```

---

## 🎉 You're Ready!

**Your EA is now:**
- ✅ Installed in MT5
- ✅ Compiled and running
- ✅ Monitoring XAUUSD
- ✅ Ready to trade

**Next steps:**
1. Let it run on demo for 1 week
2. Check Experts tab daily
3. Review all trades
4. After 1 month success → consider live
5. Always start with 0.5% risk!

---

**Good luck with your automated trading! 🚀📈**

*The EA will work 24/5 automatically. Just monitor it regularly!*
