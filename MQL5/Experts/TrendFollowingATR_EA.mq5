#property strict
#property description "Trend-following EA with H1 EMA bias, M15 confirmations, ATR SL and trailing"
#property version   "1.0.0"
#property copyright ""

#include <Trade/Trade.mqh>

// ============================
// Inputs
// ============================
input string TREND_SETUP              = "--- H1 Trend Setup ---";
input int    MA_Period_1              = 8;   // Fastest
input int    MA_Period_2              = 21;
input int    MA_Period_3              = 34;
input int    MA_Period_4              = 55;  // Slowest

input string ENTRY_SETUP              = "--- M15 Entry Setup ---";
input int    M15_MA_Period            = 21;  // For close-above/below check
input bool   Use_MACD_Confirmation    = true;
input bool   Use_RSI_Confirmation     = true;
input int    RSI_Period               = 14;

input string RISK_MANAGEMENT          = "--- Risk Management ---";
input double Risk_Per_Trade           = 0.5;   // percent of balance per trade
input int    ATR_Period               = 14;    // on H1
input double ATR_Multiplier_ISL       = 2.0;   // Initial Stop Loss multiplier
input double ATR_Multiplier_Trail     = 1.0;   // Trailing Stop distance multiplier
input bool   Use_Aggressive_Trail     = true;  // Tighten trail when profit >= 3x ATR

input string CIRCUIT_BREAKER          = "--- Circuit Breaker ---";
input double Max_Drawdown_Percent     = 10.0;  // stop trading and close all when equity drawdown >= this

// ============================
// Globals
// ============================
CTrade trade;

// Indicator handles
int hEMA_H1_1 = INVALID_HANDLE; // 8
int hEMA_H1_2 = INVALID_HANDLE; // 21
int hEMA_H1_3 = INVALID_HANDLE; // 34
int hEMA_H1_4 = INVALID_HANDLE; // 55

int hEMA_M15_1 = INVALID_HANDLE; // 8
int hEMA_M15_2 = INVALID_HANDLE; // 21 (M15_MA_Period)
int hEMA_M15_3 = INVALID_HANDLE; // 34

int hRSI_M15   = INVALID_HANDLE; // RSI 14
int hMACD_M15  = INVALID_HANDLE; // MACD 12,26,9
int hATR_H1    = INVALID_HANDLE; // ATR 14 on H1

// Bar timing
datetime lastM15ClosedBarTime = 0;
datetime lastEntryM15BarTime  = 0; // prevent duplicate entries on the same signal bar

// Circuit breaker state
bool   circuitBreakerTriggered = false;
double equityPeak              = 0.0;

// ============================
// Utilities
// ============================
string LogPrefix() { return StringFormat("[%s] ", _Symbol); }

bool CopyValue(int handle, int bufferIndex, int shift, double &out)
{
   double a[];
   if(CopyBuffer(handle, bufferIndex, shift, 1, a) <= 0) return false;
   out = a[0];
   return true;
}

bool CopyCloseValue(ENUM_TIMEFRAMES tf, int shift, double &out)
{
   double a[];
   if(CopyClose(_Symbol, tf, shift, 1, a) <= 0) return false;
   out = a[0];
   return true;
}

bool CopyTimeValue(ENUM_TIMEFRAMES tf, int shift, datetime &out)
{
   datetime a[];
   if(CopyTime(_Symbol, tf, shift, 1, a) <= 0) return false;
   out = a[0];
   return true;
}

// Rounding helper to avoid MathRound dependency in older terminals
double RoundNearest(double x)
{
   return (x >= 0.0 ? MathFloor(x + 0.5) : MathCeil(x - 0.5));
}

// Determine the number of decimal digits required by a step size (up to 8 digits)
int CountStepDigits(double step)
{
   if(step <= 0.0) return 2;
   int digits = 0;
   double v = step;
   // increase precision until v is (almost) an integer or we hit a reasonable cap
   while(digits < 8 && MathAbs(v - RoundNearest(v)) > 1e-12)
   {
      v *= 10.0;
      digits++;
   }
   return digits;
}

// Rounds volume down to the nearest step, clamped to [min,max]
double NormalizeVolumeToStep(double volume)
{
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minv = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxv = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0.0) step = 0.01;
   double steps = MathFloor(volume / step);
   double v = steps * step;
   if(v < minv) v = minv;
   if(v > maxv) v = maxv;
   int stepDigits = CountStepDigits(step);
   if(stepDigits < 0) stepDigits = 0;
   return NormalizeDouble(v, stepDigits);
}

// Ensures price is aligned to tick size and symbol digits
double NormalizePrice(double price)
{
   double tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick <= 0.0) tick = _Point;
   double n = RoundNearest(price / tick);
   double aligned = n * tick;
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   if(digits < 0) digits = 0;
   return NormalizeDouble(aligned, digits);
}

// ============================
// Trend Bias (H1) helpers
// ============================
// Returns:  1 = bullish, -1 = bearish, 0 = no bias
int GetH1TrendBias()
{
   // need EMAs on H1: 8,21,34,55
   double ema1, ema2, ema3, ema4;
   if(!CopyValue(hEMA_H1_1, 0, 0, ema1)) return 0;
   if(!CopyValue(hEMA_H1_2, 0, 0, ema2)) return 0;
   if(!CopyValue(hEMA_H1_3, 0, 0, ema3)) return 0;
   if(!CopyValue(hEMA_H1_4, 0, 0, ema4)) return 0;

   double price = (SymbolInfoDouble(_Symbol, SYMBOL_BID) + SymbolInfoDouble(_Symbol, SYMBOL_ASK)) * 0.5;

   bool bullishAlign = (ema1 > ema2 && ema2 > ema3 && ema3 > ema4);
   bool bearishAlign = (ema1 < ema2 && ema2 < ema3 && ema3 < ema4);

   if(price > ema4 && bullishAlign)
      return 1;
   if(price < ema4 && bearishAlign)
      return -1;
   return 0;
}

// ============================
// Entry checks on M15
// ============================
struct EntrySignal
{
   bool  hasSignal;
   int   direction; // 1 = buy, -1 = sell
};

EntrySignal GetM15EntrySignal()
{
   EntrySignal s; s.hasSignal = false; s.direction = 0;

   // Get closes
   double c1, c2; // closed bars: shift 1 = last closed, shift 2 = previous closed
   if(!CopyCloseValue(PERIOD_M15, 1, c1)) return s;
   if(!CopyCloseValue(PERIOD_M15, 2, c2)) return s;

   // M15 EMAs
   double ema8_1, ema21_1, ema34_1, ema21_2;
   if(!CopyValue(hEMA_M15_1, 0, 1, ema8_1)) return s;
   if(!CopyValue(hEMA_M15_2, 0, 1, ema21_1)) return s;
   if(!CopyValue(hEMA_M15_3, 0, 1, ema34_1)) return s;
   if(!CopyValue(hEMA_M15_2, 0, 2, ema21_2)) return s;

   // Ribbon alignment on M15 (8 > 21 > 34) or (8 < 21 < 34)
   bool ribbonBull = (ema8_1 > ema21_1 && ema21_1 > ema34_1);
   bool ribbonBear = (ema8_1 < ema21_1 && ema21_1 < ema34_1);

   // Price closes above/below 21 EMA; require crossover to limit repeated signals
   bool priceCrossUp   = (c1 > ema21_1 && c2 <= ema21_2);
   bool priceCrossDown = (c1 < ema21_1 && c2 >= ema21_2);

   // MACD histogram acceleration (12,26,9) on M15
   bool macdOKBull = true;
   bool macdOKBear = true;
   if(Use_MACD_Confirmation)
   {
      double macd_main_1, macd_sig_1, macd_main_2, macd_sig_2;
      if(!CopyValue(hMACD_M15, 0, 1, macd_main_1)) return s;
      if(!CopyValue(hMACD_M15, 1, 1, macd_sig_1)) return s;
      if(!CopyValue(hMACD_M15, 0, 2, macd_main_2)) return s;
      if(!CopyValue(hMACD_M15, 1, 2, macd_sig_2)) return s;

      double h1 = macd_main_1 - macd_sig_1;
      double h2 = macd_main_2 - macd_sig_2;

      macdOKBull = (h1 > 0.0 && h1 > h2);
      macdOKBear = (h1 < 0.0 && h1 < h2);
   }

   // RSI momentum crossing 50 on M15
   bool rsiOKBull = true;
   bool rsiOKBear = true;
   if(Use_RSI_Confirmation)
   {
      double rsi1, rsi2;
      if(!CopyValue(hRSI_M15, 0, 1, rsi1)) return s;
      if(!CopyValue(hRSI_M15, 0, 2, rsi2)) return s;
      rsiOKBull = (rsi2 < 50.0 && rsi1 > 50.0);
      rsiOKBear = (rsi2 > 50.0 && rsi1 < 50.0);
   }

   bool buyConditions  = priceCrossUp   && ribbonBull && macdOKBull && rsiOKBull;
   bool sellConditions = priceCrossDown && ribbonBear && macdOKBear && rsiOKBear;

   if(buyConditions)  { s.hasSignal = true; s.direction = 1; return s; }
   if(sellConditions) { s.hasSignal = true; s.direction = -1; return s; }
   return s;
}

// ============================
// Risk & position sizing
// ============================
// Calculate ATR(H1) value now
bool GetCurrentATR_H1(double &atr)
{
   return CopyValue(hATR_H1, 0, 0, atr);
}

// Calculate lot size from risk and stop distance using OrderCalcProfit
// Returns 0.0 if cannot compute
double CalculatePositionSize(int direction, double entryPrice, double stopPrice)
{
   // Risk amount in account currency
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskFraction = Risk_Per_Trade / 100.0;
   if(riskFraction < 0.0) riskFraction = 0.0;
   double riskAmount = balance * riskFraction;
   if(riskAmount <= 0.0) return 0.0;

   // Per-lot risk using OrderCalcProfit
   double perLotPL = 0.0;
   ENUM_ORDER_TYPE side = (direction > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   if(!OrderCalcProfit(side, _Symbol, 1.0, entryPrice, stopPrice, perLotPL))
      return 0.0;
   double perLotRisk = MathAbs(perLotPL);
   if(perLotRisk <= 0.0) return 0.0;

   double rawLots = riskAmount / perLotRisk;
   double lots = NormalizeVolumeToStep(rawLots);
   return lots;
}

// ============================
// Trailing stop management
// ============================
void ManageTrailingStop()
{
   if(!PositionSelect(_Symbol)) return;

   double atr;
   if(!GetCurrentATR_H1(atr)) return;

   double priceBid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double priceAsk = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0) tickSize = _Point;

   long   type     = (long)PositionGetInteger(POSITION_TYPE);
   double openPrice= PositionGetDouble(POSITION_PRICE_OPEN);
   double curSL    = PositionGetDouble(POSITION_SL);

   // Distance for trailing
   double baseTrail = ATR_Multiplier_Trail * atr;
   double profitMove = 0.0;

   if(type == POSITION_TYPE_BUY)
   {
      profitMove = priceBid - openPrice;
      double minProfitToTrail = atr; // 1x ATR
      if(profitMove >= minProfitToTrail)
      {
         double distance = baseTrail;
         if(Use_Aggressive_Trail && profitMove >= 3.0 * atr)
            distance = 0.5 * atr;

         double desiredSL = NormalizePrice(priceBid - distance);

         // Never decrease SL for buys
         if(curSL == 0.0 || desiredSL > curSL)
         {
            // Ensure SL is below current price by at least stops level
            double stopsPts = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
            double minDist  = stopsPts * _Point;
            if(minDist <= 0.0) minDist = tickSize;
            if(priceBid - desiredSL < minDist)
               desiredSL = NormalizePrice(priceBid - minDist);

            trade.PositionModify(_Symbol, desiredSL, 0.0);
         }
      }
   }
   else if(type == POSITION_TYPE_SELL)
   {
      profitMove = openPrice - priceAsk;
      double minProfitToTrail = atr; // 1x ATR
      if(profitMove >= minProfitToTrail)
      {
         double distance = baseTrail;
         if(Use_Aggressive_Trail && profitMove >= 3.0 * atr)
            distance = 0.5 * atr;

         double desiredSL = NormalizePrice(priceAsk + distance);

         // Never decrease SL for sells (i.e., SL must move down)
         if(curSL == 0.0 || desiredSL < curSL)
         {
            double stopsPts = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
            double minDist  = stopsPts * _Point;
            if(minDist <= 0.0) minDist = tickSize;
            if(desiredSL - priceAsk < minDist)
               desiredSL = NormalizePrice(priceAsk + minDist);

            trade.PositionModify(_Symbol, desiredSL, 0.0);
         }
      }
   }
}

// ============================
// Circuit breaker & one-trade logic
// ============================
void UpdateCircuitBreaker()
{
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equityPeak <= 0.0) equityPeak = equity;
   if(equity > equityPeak) equityPeak = equity;

   double ddPct = (equityPeak > 0.0 ? (equityPeak - equity) / equityPeak * 100.0 : 0.0);
   if(!circuitBreakerTriggered && ddPct >= Max_Drawdown_Percent)
   {
      circuitBreakerTriggered = true;
      Print(LogPrefix(), "Circuit breaker TRIGGERED: drawdown ", DoubleToString(ddPct, 2), "% >= ", DoubleToString(Max_Drawdown_Percent, 2), "%.");

      // Close all existing positions
      for(int i = PositionsTotal() - 1; i >= 0; --i)
      {
         if(!PositionSelectByIndex(i)) continue;
         string sym = (string)PositionGetString(POSITION_SYMBOL);
         trade.PositionClose(sym);
      }
   }
}

bool HasAnyOpenPosition()
{
   return PositionsTotal() > 0;
}

// ============================
// EA events
// ============================
int OnInit()
{
   // Create indicator handles
   hEMA_H1_1 = iMA(_Symbol, PERIOD_H1, MA_Period_1, 0, MODE_EMA, PRICE_CLOSE);
   hEMA_H1_2 = iMA(_Symbol, PERIOD_H1, MA_Period_2, 0, MODE_EMA, PRICE_CLOSE);
   hEMA_H1_3 = iMA(_Symbol, PERIOD_H1, MA_Period_3, 0, MODE_EMA, PRICE_CLOSE);
   hEMA_H1_4 = iMA(_Symbol, PERIOD_H1, MA_Period_4, 0, MODE_EMA, PRICE_CLOSE);

   hEMA_M15_1 = iMA(_Symbol, PERIOD_M15, MA_Period_1, 0, MODE_EMA, PRICE_CLOSE);
   hEMA_M15_2 = iMA(_Symbol, PERIOD_M15, M15_MA_Period, 0, MODE_EMA, PRICE_CLOSE);
   hEMA_M15_3 = iMA(_Symbol, PERIOD_M15, MA_Period_3, 0, MODE_EMA, PRICE_CLOSE);

   hRSI_M15  = iRSI(_Symbol, PERIOD_M15, RSI_Period, PRICE_CLOSE);
   hMACD_M15 = iMACD(_Symbol, PERIOD_M15, 12, 26, 9, PRICE_CLOSE);
   hATR_H1   = iATR(_Symbol, PERIOD_H1, ATR_Period);

   if(hEMA_H1_1==INVALID_HANDLE || hEMA_H1_2==INVALID_HANDLE || hEMA_H1_3==INVALID_HANDLE || hEMA_H1_4==INVALID_HANDLE ||
      hEMA_M15_1==INVALID_HANDLE || hEMA_M15_2==INVALID_HANDLE || hEMA_M15_3==INVALID_HANDLE ||
      hRSI_M15==INVALID_HANDLE || hMACD_M15==INVALID_HANDLE || hATR_H1==INVALID_HANDLE)
   {
      Print(LogPrefix(), "Failed to create indicator handles.");
      return INIT_FAILED;
   }

   // Initialize M15 bar time
   if(!CopyTimeValue(PERIOD_M15, 1, lastM15ClosedBarTime)) lastM15ClosedBarTime = 0;
   lastEntryM15BarTime = 0;

   equityPeak = AccountInfoDouble(ACCOUNT_EQUITY);
   circuitBreakerTriggered = false;

   Print(LogPrefix(), "EA initialized.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hEMA_H1_1!=INVALID_HANDLE) IndicatorRelease(hEMA_H1_1);
   if(hEMA_H1_2!=INVALID_HANDLE) IndicatorRelease(hEMA_H1_2);
   if(hEMA_H1_3!=INVALID_HANDLE) IndicatorRelease(hEMA_H1_3);
   if(hEMA_H1_4!=INVALID_HANDLE) IndicatorRelease(hEMA_H1_4);
   if(hEMA_M15_1!=INVALID_HANDLE) IndicatorRelease(hEMA_M15_1);
   if(hEMA_M15_2!=INVALID_HANDLE) IndicatorRelease(hEMA_M15_2);
   if(hEMA_M15_3!=INVALID_HANDLE) IndicatorRelease(hEMA_M15_3);
   if(hRSI_M15!=INVALID_HANDLE)   IndicatorRelease(hRSI_M15);
   if(hMACD_M15!=INVALID_HANDLE)  IndicatorRelease(hMACD_M15);
   if(hATR_H1!=INVALID_HANDLE)    IndicatorRelease(hATR_H1);
}

void OnTick()
{
   // Update circuit breaker and possibly close positions
   UpdateCircuitBreaker();

   // Always manage trailing if any position exists
   ManageTrailingStop();

   if(circuitBreakerTriggered)
      return; // do not open new positions

   // Only one trade at a time (global)
   if(HasAnyOpenPosition())
      return;

   // Entry logic only on a new M15 closed bar
   datetime currClosedM15;
   if(!CopyTimeValue(PERIOD_M15, 1, currClosedM15)) return;
   if(currClosedM15 == lastM15ClosedBarTime)
      return; // no new closed bar yet

   lastM15ClosedBarTime = currClosedM15;

   // Check H1 bias
   int bias = GetH1TrendBias();
   if(bias == 0) return;

   // Check M15 entry signal (ALL confirmations must be true if enabled)
   EntrySignal sig = GetM15EntrySignal();
   if(!sig.hasSignal) return;

   // align with H1 bias
   if(sig.direction != bias) return;

   // Deduplicate per signal bar
   if(lastEntryM15BarTime == currClosedM15)
      return;

   // Compute ATR(H1) and initial SL
   double atr;
   if(!GetCurrentATR_H1(atr)) return;
   double entryPriceBuy = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double entryPriceSell= SymbolInfoDouble(_Symbol, SYMBOL_BID);

   double slPrice = 0.0;
   if(sig.direction > 0)
      slPrice = NormalizePrice(entryPriceBuy - ATR_Multiplier_ISL * atr);
   else
      slPrice = NormalizePrice(entryPriceSell + ATR_Multiplier_ISL * atr);

   // Respect stops level
   double stopsPts = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDist  = stopsPts * _Point;
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(minDist <= 0.0) minDist = (tickSize > 0 ? tickSize : _Point);

   if(sig.direction > 0)
   {
      if(entryPriceBuy - slPrice < minDist)
         slPrice = NormalizePrice(entryPriceBuy - minDist);
   }
   else
   {
      if(slPrice - entryPriceSell < minDist)
         slPrice = NormalizePrice(entryPriceSell + minDist);
   }

   // Position sizing
   double lots = (sig.direction > 0)
                 ? CalculatePositionSize(1,  entryPriceBuy,  slPrice)
                 : CalculatePositionSize(-1, entryPriceSell, slPrice);

   if(lots <= 0.0)
   {
      Print(LogPrefix(), "Calculated lot size is zero; skipping trade.");
      return;
   }

   // Send market order with SL, no TP
   bool sent = false;
   if(sig.direction > 0)
   {
      sent = trade.Buy(lots, _Symbol, 0.0, slPrice, 0.0);
   }
   else
   {
      sent = trade.Sell(lots, _Symbol, 0.0, slPrice, 0.0);
   }

   if(sent)
   {
      lastEntryM15BarTime = currClosedM15;
      Print(LogPrefix(), (sig.direction>0?"BUY":"SELL"), " opened. Lots=", DoubleToString(lots,2), ", SL=", DoubleToString(slPrice, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS)));
   }
   else
   {
      Print(LogPrefix(), "Order send failed. Retcode=", (int)trade.ResultRetcode(), ", comment=", trade.ResultRetcodeDescription());
   }
}

// ============================
// Notes
// - This EA does not guarantee profits.
// - Thorough backtesting and forward testing are required.
// - Ensure trading permissions and symbol settings (lot step, stops) are compatible.
