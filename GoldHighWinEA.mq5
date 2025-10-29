#property copyright "Cursor Assistant"
#property link      ""
#property version   "1.00"
#property strict
#property description "High-Win-Rate Gold EA (XAUUSD) for MT5: EMA ribbon (8/21/50), RSI(14), Stochastic(5,3,3) confirmations, ATR-based SL/TP and optional trailing, optional Pivot filter, spread/session filters, risk-based sizing, logging and notifications."

#include <Trade/Trade.mqh>

//==================== Inputs: General ====================
input bool   RestrictToXAUUSD           = true;     // Trade only XAUUSD-like symbols
input bool   AllowNewPositions          = true;     // Allow opening new positions
input bool   EnforceM5orM15Only         = true;     // Only operate on M5 or M15
input ENUM_TIMEFRAMES SignalTimeframe   = PERIOD_CURRENT; // Indicator timeframe (PERIOD_CURRENT=M5/M15 chart)
input uint   MagicNumber                = 560028;   // Magic number
input int    OrderDeviationPoints       = 20;       // Max price deviation in points

//==================== Inputs: Risk & Limits ====================
input double RiskPercentPerTrade        = 0.7;      // % of equity risked per trade (0.5-1.0)
input int    MaxOpenPositions           = 1;        // Max simultaneous positions (1-3)
input int    MaxSpreadPoints            = 80;       // Only trade if spread <= this (points)

//==================== Inputs: Indicators ====================
input int    EmaFastPeriod              = 8;
input int    EmaMidPeriod               = 21;
input int    EmaSlowPeriod              = 50;
input int    RsiPeriod                  = 14;
input int    StochK                     = 5;
input int    StochD                     = 3;
input int    StochSlowing               = 3;
input int    AtrPeriod                  = 14;

//==================== Inputs: Entry Thresholds ====================
input double RsiLongMin                 = 45.0;     // RSI lower bound for longs
input double RsiLongMax                 = 70.0;     // RSI upper bound for longs
input double RsiShortMin                = 30.0;     // RSI lower bound for shorts
input double RsiShortMax                = 55.0;     // RSI upper bound for shorts
input int    StochOversold              = 20;       // Stochastic oversold threshold
input int    StochOverbought            = 80;       // Stochastic overbought threshold
input bool   OnlyOneSignalPerBar        = true;     // Prevent multiple opens per bar

//==================== Inputs: Exits (ATR-based) ====================
input double SL_ATR_Multiplier          = 1.0;      // SL distance as ATR multiple
input double TP_ATR_Multiplier          = 0.6;      // TP distance as ATR multiple (smaller to favor win rate)
input bool   UseATRTrailingStop         = true;     // Enable ATR trailing stop
input double Trail_ATR_Multiplier       = 1.2;      // Trailing distance as ATR multiple

//==================== Inputs: Sessions & Liquidity ====================
input bool   UseSessionFilter           = true;     // Trade only during sessions below
input int    Session1StartHour          = 7;        // Session 1 start hour (broker time)
input int    Session1EndHour            = 12;       // Session 1 end hour (exclusive)
input int    Session2StartHour          = 13;       // Session 2 start hour (broker time)
input int    Session2EndHour            = 21;       // Session 2 end hour (exclusive)
input bool   AvoidRollover              = true;     // Avoid low-liquidity rollover window
input int    RolloverStartHour          = 21;       // Rollover start hour (broker time)
input int    RolloverStartMinute        = 55;       // Rollover start minute
input int    RolloverEndHour            = 23;       // Rollover end hour (broker time)
input int    RolloverEndMinute          = 5;        // Rollover end minute

//==================== Inputs: Pivot Filter (Optional) ====================
input bool   UsePivotFilter             = false;    // Require price near pivot/support/resistance
input double PivotProximityATR          = 0.30;     // Max distance to pivot level in ATRs

//==================== Inputs: Notifications ====================
input bool   UsePushNotifications       = false;    // Send push notifications for trade events

//==============================================================
CTrade trade;

// Indicator handles
int    hEMA8   = INVALID_HANDLE;
int    hEMA21  = INVALID_HANDLE;
int    hEMA50  = INVALID_HANDLE;
int    hRSI    = INVALID_HANDLE;
int    hSTOCH  = INVALID_HANDLE;
int    hATR    = INVALID_HANDLE;

// State
datetime g_lastBarTime = 0;
ENUM_TIMEFRAMES g_tf = PERIOD_CURRENT;

//------------------ Utility functions ------------------
bool isSymbolGold(const string symbol)
{
   if(!RestrictToXAUUSD) return true;
   // Accept common gold symbols: XAUUSD, XAUUSD.*, GOLD, etc.
   if(StringFind(symbol, "XAUUSD", 0) >= 0) return true;
   if(StringFind(symbol, "XAU", 0) >= 0)    return true;
   if(StringFind(symbol, "GOLD", 0) >= 0)   return true;
   return false;
}

bool isAllowedTimeframe(ENUM_TIMEFRAMES tf)
{
   if(!EnforceM5orM15Only) return true;
   return (tf == PERIOD_M5 || tf == PERIOD_M15);
}

int countOpenPositionsForThisEA()
{
   int count = 0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(PositionSelectByIndex(i))
      {
         string sym = PositionGetString(POSITION_SYMBOL);
         long   mg  = (long)PositionGetInteger(POSITION_MAGIC);
         if(sym == _Symbol && mg == (long)MagicNumber)
            count++;
      }
   }
   return count;
}

bool isSpreadOk()
{
   double ask = 0.0, bid = 0.0;
   if(!SymbolInfoDouble(_Symbol, SYMBOL_ASK, ask)) return false;
   if(!SymbolInfoDouble(_Symbol, SYMBOL_BID, bid)) return false;
   double spreadPoints = (ask - bid) / _Point;
   return (spreadPoints <= MaxSpreadPoints);
}

int minutesOfDay(int hour, int minute)
{
   return hour * 60 + minute;
}

bool inRolloverWindow()
{
   if(!AvoidRollover) return false;
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   int nowMin = minutesOfDay(t.hour, t.min);
   int startMin = minutesOfDay(RolloverStartHour, RolloverStartMinute);
   int endMin   = minutesOfDay(RolloverEndHour,   RolloverEndMinute);
   if(startMin <= endMin)
      return (nowMin >= startMin && nowMin < endMin);
   // window wraps past midnight
   return (nowMin >= startMin || nowMin < endMin);
}

bool isWithinSessions()
{
   if(!UseSessionFilter) return true;
   if(inRolloverWindow()) return false;
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   int nowMin = minutesOfDay(t.hour, t.min);
   int s1Start = minutesOfDay(Session1StartHour, 0);
   int s1End   = minutesOfDay(Session1EndHour,   0);
   int s2Start = minutesOfDay(Session2StartHour, 0);
   int s2End   = minutesOfDay(Session2EndHour,   0);
   bool inS1 = (nowMin >= s1Start && nowMin < s1End);
   bool inS2 = (nowMin >= s2Start && nowMin < s2End);
   return (inS1 || inS2);
}

bool getBarTime(datetime &barTime)
{
   datetime t[1];
   if(CopyTime(_Symbol, g_tf, 0, 1, t) != 1)
      return false;
   barTime = t[0];
   return true;
}

// Get last closed bar value from a handle buffer (shift=1)
bool getIndicatorValue(int handle, int bufferIndex, int shift, double &out)
{
   if(handle == INVALID_HANDLE) return false;
   double data[2];
   if(CopyBuffer(handle, bufferIndex, shift, 1, data) != 1)
      return false;
   out = data[0];
   return true;
}

bool getTwoIndicatorValues(int handle, int bufferIndex, int shift, double &curr, double &prev)
{
   if(handle == INVALID_HANDLE) return false;
   double data[2];
   if(CopyBuffer(handle, bufferIndex, shift, 2, data) != 2)
      return false;
   curr = data[0]; // shift
   prev = data[1]; // shift+1
   return true;
}

// ATR helper (shift=1 for last closed bar)
double getATR(int shift)
{
   double atr = 0.0;
   if(!getIndicatorValue(hATR, 0, shift, atr))
      return 0.0;
   return atr;
}

//------------------ Pivot Points ------------------
struct PivotLevels
{
   double P;
   double R1; double R2; double R3;
   double S1; double S2; double S3;
};

bool computeDailyPivots(PivotLevels &p)
{
   double H = iHigh(_Symbol, PERIOD_D1, 1);
   double L = iLow(_Symbol,  PERIOD_D1, 1);
   double C = iClose(_Symbol, PERIOD_D1, 1);
   if(H <= 0.0 || L <= 0.0 || C <= 0.0)
      return false;
   p.P  = (H + L + C) / 3.0;
   p.R1 = 2.0 * p.P - L;
   p.S1 = 2.0 * p.P - H;
   p.R2 = p.P + (H - L);
   p.S2 = p.P - (H - L);
   p.R3 = H + 2.0 * (p.P - L);
   p.S3 = L - 2.0 * (H - p.P);
   return true;
}

bool nearAny(const double price, const double *levels, int n, const double maxDistance)
{
   for(int i = 0; i < n; i++)
   {
      if(MathAbs(price - levels[i]) <= maxDistance)
         return true;
   }
   return false;
}

bool nearLongPivots(double refPrice, double maxDist)
{
   if(!UsePivotFilter) return true;
   PivotLevels p;
   if(!computeDailyPivots(p)) return false; // if can't compute, block trades when filter is enabled
   double lvls[4] = {p.P, p.S1, p.S2, p.S3};
   return nearAny(refPrice, lvls, 4, maxDist);
}

bool nearShortPivots(double refPrice, double maxDist)
{
   if(!UsePivotFilter) return true;
   PivotLevels p;
   if(!computeDailyPivots(p)) return false;
   double lvls[4] = {p.P, p.R1, p.R2, p.R3};
   return nearAny(refPrice, lvls, 4, maxDist);
}

//------------------ Signals ------------------
bool stochCrossUpFromOversold()
{
   double kCurr, kPrev, dCurr, dPrev;
   if(!getTwoIndicatorValues(hSTOCH, 0, 1, kCurr, kPrev)) return false; // %K
   if(!getTwoIndicatorValues(hSTOCH, 1, 1, dCurr, dPrev)) return false; // %D
   // Cross up: K crosses above D on last closed bar; and previous K was in oversold region
   bool crossedUp = (kPrev <= dPrev && kCurr > dCurr);
   bool wasOversold = (kPrev < StochOversold && dPrev < StochOversold);
   return (crossedUp && wasOversold);
}

bool stochCrossDownFromOverbought()
{
   double kCurr, kPrev, dCurr, dPrev;
   if(!getTwoIndicatorValues(hSTOCH, 0, 1, kCurr, kPrev)) return false; // %K
   if(!getTwoIndicatorValues(hSTOCH, 1, 1, dCurr, dPrev)) return false; // %D
   // Cross down: K crosses below D; and previous K was overbought
   bool crossedDown = (kPrev >= dPrev && kCurr < dCurr);
   bool wasOverbought = (kPrev > StochOverbought && dPrev > StochOverbought);
   return (crossedDown && wasOverbought);
}

bool checkLongSignal()
{
   // EMA ribbon and price filter
   double ema8, ema21, ema50;
   if(!getIndicatorValue(hEMA8,  0, 1, ema8))  return false;
   if(!getIndicatorValue(hEMA21, 0, 1, ema21)) return false;
   if(!getIndicatorValue(hEMA50, 0, 1, ema50)) return false;

   double closePrev = iClose(_Symbol, g_tf, 1);
   if(closePrev <= 0.0) return false;

   if(!(closePrev > ema50)) return false;                   // Price above EMA50
   if(!(ema8 > ema21 && ema21 > ema50)) return false;       // EMA 8 > 21 > 50

   double rsi;
   if(!getIndicatorValue(hRSI, 0, 1, rsi)) return false;
   if(!(rsi >= RsiLongMin && rsi <= RsiLongMax)) return false; // RSI range

   if(!stochCrossUpFromOversold()) return false;            // Stoch cross up

   // Optional pivot proximity (use ATR * PivotProximityATR)
   double atr = getATR(1);
   if(atr <= 0.0) return false;
   if(!nearLongPivots(closePrev, atr * PivotProximityATR)) return false;

   return true;
}

bool checkShortSignal()
{
   double ema8, ema21, ema50;
   if(!getIndicatorValue(hEMA8,  0, 1, ema8))  return false;
   if(!getIndicatorValue(hEMA21, 0, 1, ema21)) return false;
   if(!getIndicatorValue(hEMA50, 0, 1, ema50)) return false;

   double closePrev = iClose(_Symbol, g_tf, 1);
   if(closePrev <= 0.0) return false;

   if(!(closePrev < ema50)) return false;                   // Price below EMA50
   if(!(ema8 < ema21 && ema21 < ema50)) return false;       // EMA 8 < 21 < 50

   double rsi;
   if(!getIndicatorValue(hRSI, 0, 1, rsi)) return false;
   if(!(rsi >= RsiShortMin && rsi <= RsiShortMax)) return false; // RSI range

   if(!stochCrossDownFromOverbought()) return false;        // Stoch cross down

   double atr = getATR(1);
   if(atr <= 0.0) return false;
   if(!nearShortPivots(closePrev, atr * PivotProximityATR)) return false;

   return true;
}

//------------------ Sizing ------------------

double normalizeVolumeToStep(double lots)
{
   double vMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double vStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(vStep <= 0.0) vStep = 0.01;
   lots = MathMax(vMin, MathMin(vMax, lots));
   // round down to step to not exceed risk
   lots = MathFloor(lots / vStep) * vStep;
   lots = NormalizeDouble(lots, 2);
   return lots;
}

// Calculate lot size from risk % and SL distance
// Returns 0.0 if cannot size safely

double calcLotsByRisk(double entryPrice, double slPrice)
{
   double riskPct = MathMax(0.01, RiskPercentPerTrade);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskMoney = equity * (riskPct / 100.0);

   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0.0 || tickValue <= 0.0) return 0.0;

   double priceDist = MathAbs(entryPrice - slPrice);
   if(priceDist <= 0.0) return 0.0;

   // money per 1 lot for given price distance
   double ticks = priceDist / tickSize;
   double moneyPerLot = ticks * tickValue;
   if(moneyPerLot <= 0.0) return 0.0;

   double lots = riskMoney / moneyPerLot;
   lots = normalizeVolumeToStep(lots);
   return lots;
}

//------------------ Trade execution ------------------

bool openBuy()
{
   double atr = getATR(1);
   if(atr <= 0.0) return false;

   double ask = 0.0; SymbolInfoDouble(_Symbol, SYMBOL_ASK, ask);
   double sl = ask - SL_ATR_Multiplier * atr;
   double tp = ask + TP_ATR_Multiplier * atr;
   sl = NormalizeDouble(sl, _Digits);
   tp = NormalizeDouble(tp, _Digits);

   double lots = calcLotsByRisk(ask, sl);
   if(lots <= 0.0) { Print("Lot sizing failed for BUY"); return false; }

   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(OrderDeviationPoints);
   bool ok = trade.Buy(lots, _Symbol, 0.0, sl, tp, "GoldEA BUY");
   if(ok)
   {
      PrintFormat("BUY opened: lots=%.2f entry=%.2f SL=%.2f TP=%.2f", lots, ask, sl, tp);
      if(UsePushNotifications)
      {
         string msg = StringFormat("BUY %s %.2f lots @ %.2f SL %.2f TP %.2f", _Symbol, lots, ask, sl, tp);
         SendNotification(msg);
      }
   }
   else
   {
      PrintFormat("BUY failed: retcode=%d, err=%d", trade.ResultRetcode(), GetLastError());
   }
   return ok;
}

bool openSell()
{
   double atr = getATR(1);
   if(atr <= 0.0) return false;

   double bid = 0.0; SymbolInfoDouble(_Symbol, SYMBOL_BID, bid);
   double sl = bid + SL_ATR_Multiplier * atr;
   double tp = bid - TP_ATR_Multiplier * atr;
   sl = NormalizeDouble(sl, _Digits);
   tp = NormalizeDouble(tp, _Digits);

   double lots = calcLotsByRisk(bid, sl);
   if(lots <= 0.0) { Print("Lot sizing failed for SELL"); return false; }

   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(OrderDeviationPoints);
   bool ok = trade.Sell(lots, _Symbol, 0.0, sl, tp, "GoldEA SELL");
   if(ok)
   {
      PrintFormat("SELL opened: lots=%.2f entry=%.2f SL=%.2f TP=%.2f", lots, bid, sl, tp);
      if(UsePushNotifications)
      {
         string msg = StringFormat("SELL %s %.2f lots @ %.2f SL %.2f TP %.2f", _Symbol, lots, bid, sl, tp);
         SendNotification(msg);
      }
   }
   else
   {
      PrintFormat("SELL failed: retcode=%d, err=%d", trade.ResultRetcode(), GetLastError());
   }
   return ok;
}

void manageTrailingStops()
{
   if(!UseATRTrailingStop) return;
   double atr = getATR(1);
   if(atr <= 0.0) return;

   int total = PositionsTotal();
   for(int i = 0; i < total; i++)
   {
      if(!PositionSelectByIndex(i)) continue;
      string sym = PositionGetString(POSITION_SYMBOL);
      long   mg  = (long)PositionGetInteger(POSITION_MAGIC);
      if(sym != _Symbol || mg != (long)MagicNumber) continue;

      ulong ticket = (ulong)PositionGetInteger(POSITION_TICKET);
      long  type   = (long)PositionGetInteger(POSITION_TYPE);
      double open  = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl    = PositionGetDouble(POSITION_SL);
      double tp    = PositionGetDouble(POSITION_TP);

      double ask=0.0, bid=0.0;
      SymbolInfoDouble(_Symbol, SYMBOL_ASK, ask);
      SymbolInfoDouble(_Symbol, SYMBOL_BID, bid);

      int    stopLevel = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
      double minDist   = stopLevel * _Point;

      if(type == POSITION_TYPE_BUY)
      {
         double desiredSL = bid - Trail_ATR_Multiplier * atr;
         if(sl == 0.0 || desiredSL > sl)
         {
            double newSL = NormalizeDouble(desiredSL, _Digits);
            if((bid - newSL) >= minDist)
               trade.PositionModify(ticket, newSL, tp);
         }
      }
      else if(type == POSITION_TYPE_SELL)
      {
         double desiredSL = ask + Trail_ATR_Multiplier * atr;
         if(sl == 0.0 || desiredSL < sl)
         {
            double newSL = NormalizeDouble(desiredSL, _Digits);
            if((newSL - ask) >= minDist)
               trade.PositionModify(ticket, newSL, tp);
         }
      }
   }
}

//------------------ Engine ------------------

void onNewBar()
{
   if(!AllowNewPositions) return;
   if(countOpenPositionsForThisEA() >= MaxOpenPositions) return;
   if(!isSpreadOk()) return;
   if(!isWithinSessions()) return;

   // Evaluate signals on last closed bar
   bool longSignal = checkLongSignal();
   bool shortSignal = checkShortSignal();

   // Prefer single direction per bar; choose one if both true (rare)
   if(longSignal && !shortSignal)
   {
      openBuy();
   }
   else if(shortSignal && !longSignal)
   {
      openSell();
   }
   else if(longSignal && shortSignal)
   {
      // If both, choose direction of EMA slope bias: compare ema8-ema21 delta
      double ema8, ema21; getIndicatorValue(hEMA8, 0, 1, ema8); getIndicatorValue(hEMA21, 0, 1, ema21);
      if(ema8 >= ema21) openBuy(); else openSell();
   }
}

//------------------ MT5 events ------------------

int OnInit()
{
   if(!isSymbolGold(_Symbol))
   {
      Print("Symbol is not recognized as XAUUSD; trading disabled due to RestrictToXAUUSD.");
      return(INIT_PARAMETERS_INCORRECT);
   }

   g_tf = (SignalTimeframe == PERIOD_CURRENT ? (ENUM_TIMEFRAMES)Period() : SignalTimeframe);
   if(!isAllowedTimeframe(g_tf))
   {
      Print("Timeframe not allowed (only M5 or M15). Change chart or SignalTimeframe.");
      return(INIT_PARAMETERS_INCORRECT);
   }

   hEMA8  = iMA(_Symbol, g_tf, EmaFastPeriod, 0, MODE_EMA, PRICE_CLOSE);
   hEMA21 = iMA(_Symbol, g_tf, EmaMidPeriod,  0, MODE_EMA, PRICE_CLOSE);
   hEMA50 = iMA(_Symbol, g_tf, EmaSlowPeriod, 0, MODE_EMA, PRICE_CLOSE);
   hRSI   = iRSI(_Symbol, g_tf, RsiPeriod, PRICE_CLOSE);
   hSTOCH = iStochastic(_Symbol, g_tf, StochK, StochD, StochSlowing, MODE_SMA, STO_LOWHIGH);
   hATR   = iATR(_Symbol, g_tf, AtrPeriod);

   if(hEMA8 == INVALID_HANDLE || hEMA21 == INVALID_HANDLE || hEMA50 == INVALID_HANDLE ||
      hRSI  == INVALID_HANDLE || hSTOCH == INVALID_HANDLE || hATR   == INVALID_HANDLE)
   {
      Print("Indicator handle creation failed.");
      return(INIT_FAILED);
   }

   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(OrderDeviationPoints);

   if(!getBarTime(g_lastBarTime))
      g_lastBarTime = 0;

   Print("GoldHighWinEA initialized. Timeframe=", EnumToString(g_tf));
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(hEMA8  != INVALID_HANDLE) IndicatorRelease(hEMA8);
   if(hEMA21 != INVALID_HANDLE) IndicatorRelease(hEMA21);
   if(hEMA50 != INVALID_HANDLE) IndicatorRelease(hEMA50);
   if(hRSI   != INVALID_HANDLE) IndicatorRelease(hRSI);
   if(hSTOCH != INVALID_HANDLE) IndicatorRelease(hSTOCH);
   if(hATR   != INVALID_HANDLE) IndicatorRelease(hATR);
}

void OnTick()
{
   // Manage trailing stops continuously
   manageTrailingStops();

   // Only act on new bars if configured
   if(OnlyOneSignalPerBar)
   {
      datetime bt = 0;
      if(getBarTime(bt))
      {
         if(bt != g_lastBarTime)
         {
            g_lastBarTime = bt;
            onNewBar();
         }
      }
      return;
   }

   // If not restricting to bar-open, we can evaluate on each tick sparingly
   static datetime lastEval = 0;
   if(TimeCurrent() - lastEval >= 10) // evaluate at most every 10 seconds
   {
      lastEval = TimeCurrent();
      onNewBar();
   }
}

void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
{
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
   {
      long dealType = (long)trans.deal_type;
      string sym    = trans.symbol;
      double price  = trans.price;
      double profit = trans.profit;
      if(trans.entry == DEAL_ENTRY_IN)
      {
         if(dealType == DEAL_TYPE_BUY)
            PrintFormat("DEAL OPEN BUY %s @ %.2f", sym, price);
         else if(dealType == DEAL_TYPE_SELL)
            PrintFormat("DEAL OPEN SELL %s @ %.2f", sym, price);
         if(UsePushNotifications)
            SendNotification(StringFormat("Opened %s %s @ %.2f", (dealType==DEAL_TYPE_BUY?"BUY":"SELL"), sym, price));
      }
      else if(trans.entry == DEAL_ENTRY_OUT)
      {
         PrintFormat("DEAL CLOSE %s %s @ %.2f P/L=%.2f", sym, (dealType==DEAL_TYPE_SELL?"SELL":"BUY"), price, profit);
         if(UsePushNotifications)
            SendNotification(StringFormat("Closed %s P/L %.2f", sym, profit));
      }
   }
}
