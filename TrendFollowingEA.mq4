#property strict
#property copyright "AI Assistant"
#property version   "1.0"
#property description "Trend-Following EA: H1 bias, M15 confirmations, ATR risk mgmt and trailing stop"

// =============================
// Inputs
// =============================
// Trend & Entry Parameters
input string TREND_SETUP = "--- H1 Trend Setup ---";
input int MA_Period_1 = 8;   // Fastest EMA
input int MA_Period_2 = 21;  // EMA
input int MA_Period_3 = 34;  // EMA
input int MA_Period_4 = 55;  // Slowest EMA

input string ENTRY_SETUP = "--- M15 Entry Setup ---";
input int M15_MA_Period = 21;                // M15 MA for price close condition
input bool Use_MACD_Confirmation = true;
input bool Use_RSI_Confirmation = true;
input int RSI_Period = 14;

// Risk Management
input string RISK_MANAGEMENT = "--- Risk Management ---";
input double Risk_Per_Trade = 0.5;           // Risk % per trade (0.5 = 0.5%)
input int ATR_Period = 14;
input double ATR_Multiplier_ISL = 2.0;       // Multiplier for Initial Stop Loss
input double ATR_Multiplier_Trail = 1.0;     // Multiplier for Trailing Stop distance
input bool Use_Aggressive_Trail = true;      // Tighten trail on big profits (>3x ATR)

// Circuit Breaker
input double Max_Drawdown_Percent = 10.0;    // Stop trading and close all if equity drops this percent from peak

// Misc
input int MagicNumber = 20251030;
input int Slippage = 3;

// =============================
// Globals
// =============================
datetime g_lastProcessedM15BarTime = 0;
double   g_peakEquity = 0.0;
bool     g_circuitTripped = false;

// =============================
// Utility helpers
// =============================
double GetPoint()
{
   // handle 3/5-digit brokers properly using _Point
   return(_Point);
}

double GetTickSize()
{
   return(MarketInfo(Symbol(), MODE_TICKSIZE));
}

double GetTickValue()
{
   return(MarketInfo(Symbol(), MODE_TICKVALUE));
}

double NormalizeLot(double lots)
{
   double minLot  = MarketInfo(Symbol(), MODE_MINLOT);
   double maxLot  = MarketInfo(Symbol(), MODE_MAXLOT);
   double stepLot = MarketInfo(Symbol(), MODE_LOTSTEP);
   if (lots < minLot) lots = minLot;
   if (lots > maxLot) lots = maxLot;
   // round down to step
   int steps = (int)MathFloor((lots - minLot + 1e-12) / stepLot);
   double norm = minLot + steps * stepLot;
   if (norm < minLot) norm = minLot;
   if (norm > maxLot) norm = maxLot;
   return(NormalizeDouble(norm, 2));
}

int GetStopLevelPoints()
{
   int stopLevel = (int)MarketInfo(Symbol(), MODE_STOPLEVEL); // in points
   return(stopLevel);
}

bool HasOpenPosition()
{
   for (int i=0; i<OrdersTotal(); i++)
   {
      if (OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
      {
         if (OrderSymbol() == Symbol() && OrderMagicNumber() == MagicNumber)
         {
            return(true);
         }
      }
   }
   return(false);
}

bool CloseAllPositions()
{
   bool allClosed = true;
   for (int i=OrdersTotal()-1; i>=0; i--)
   {
      if (OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
      {
         if (OrderSymbol() == Symbol() && OrderMagicNumber() == MagicNumber)
         {
            int type = OrderType();
            double lots = OrderLots();
            bool result = false;
            if (type == OP_BUY)
               result = OrderClose(OrderTicket(), lots, Bid, Slippage, clrRed);
            else if (type == OP_SELL)
               result = OrderClose(OrderTicket(), lots, Ask, Slippage, clrRed);
            else
               result = OrderDelete(OrderTicket());
            if (!result) allClosed = false;
         }
      }
   }
   return(allClosed);
}

// =============================
// Indicator getters
// =============================
double GetATR_H1(int shift)
{
   return(iATR(Symbol(), PERIOD_H1, ATR_Period, shift));
}

double GetEMA(int period, int timeframe, int shift)
{
   return(iMA(Symbol(), timeframe, period, 0, MODE_EMA, PRICE_CLOSE, shift));
}

double GetMACDMain(int fast, int slow, int signal, int timeframe, int shift)
{
   return(iMACD(Symbol(), timeframe, fast, slow, signal, PRICE_CLOSE, MODE_MAIN, shift));
}

double GetMACDSignal(int fast, int slow, int signal, int timeframe, int shift)
{
   return(iMACD(Symbol(), timeframe, fast, slow, signal, PRICE_CLOSE, MODE_SIGNAL, shift));
}

double GetRSI(int period, int timeframe, int shift)
{
   return(iRSI(Symbol(), timeframe, period, PRICE_CLOSE, shift));
}

// =============================
// Bias and entry checks
// =============================
// Returns 1 for bullish, -1 for bearish, 0 for none
int GetH1TrendBias()
{
   double ema8  = GetEMA(MA_Period_1, PERIOD_H1, 0);
   double ema21 = GetEMA(MA_Period_2, PERIOD_H1, 0);
   double ema34 = GetEMA(MA_Period_3, PERIOD_H1, 0);
   double ema55 = GetEMA(MA_Period_4, PERIOD_H1, 0);
   double price = iClose(Symbol(), PERIOD_H1, 0);

   bool bullish = (price > ema55) && (ema8 > ema21) && (ema21 > ema34) && (ema34 > ema55);
   bool bearish = (price < ema55) && (ema8 < ema21) && (ema21 < ema34) && (ema34 < ema55);

   if (bullish) return 1;
   if (bearish) return -1;
   return 0;
}

bool CheckM15MAConfirmations(int direction)
{
   // Evaluate on last closed bar (shift=1)
   int tf = PERIOD_M15;
   int s  = 1;
   double close1 = iClose(Symbol(), tf, s);

   double ema8  = GetEMA(MA_Period_1, tf, s);
   double ema21 = GetEMA(MA_Period_2, tf, s);
   double ema34 = GetEMA(MA_Period_3, tf, s);
   double ema21_price = iMA(Symbol(), tf, M15_MA_Period, 0, MODE_EMA, PRICE_CLOSE, s);

   if (direction > 0)
   {
      bool priceAbove21 = (close1 > ema21_price);
      bool align = (ema8 > ema21) && (ema21 > ema34);
      return priceAbove21 && align;
   }
   else if (direction < 0)
   {
      bool priceBelow21 = (close1 < ema21_price);
      bool align = (ema8 < ema21) && (ema21 < ema34);
      return priceBelow21 && align;
   }
   return false;
}

bool CheckM15MACDConfirmations(int direction)
{
   if (!Use_MACD_Confirmation) return true;
   int tf = PERIOD_M15;
   // histogram = main - signal on closed bars 1 and 2
   double main1   = GetMACDMain(12, 26, 9, tf, 1);
   double signal1 = GetMACDSignal(12, 26, 9, tf, 1);
   double hist1   = main1 - signal1;

   double main2   = GetMACDMain(12, 26, 9, tf, 2);
   double signal2 = GetMACDSignal(12, 26, 9, tf, 2);
   double hist2   = main2 - signal2;

   if (direction > 0)
      return (hist1 > 0.0) && (hist1 > hist2);
   else if (direction < 0)
      return (hist1 < 0.0) && (hist1 < hist2);
   return false;
}

bool CheckM15RSIConfirmations(int direction)
{
   if (!Use_RSI_Confirmation) return true;
   int tf = PERIOD_M15;
   double rsiPrev = GetRSI(RSI_Period, tf, 2);
   double rsiCurr = GetRSI(RSI_Period, tf, 1);

   if (direction > 0)
      return (rsiPrev < 50.0 && rsiCurr > 50.0);
   else if (direction < 0)
      return (rsiPrev > 50.0 && rsiCurr < 50.0);
   return false;
}

// =============================
// Position sizing
// =============================
// Compute lots based on risk % and stop distance (price distance)
double ComputeLotsByRisk(double stopDistancePrice)
{
   if (stopDistancePrice <= 0.0) return 0.0;
   double riskMoney = AccountBalance() * (Risk_Per_Trade / 100.0);
   double tickSize  = GetTickSize();
   double tickValue = GetTickValue();
   if (tickSize <= 0.0 || tickValue <= 0.0) return 0.0;

   double ticksAtStop = stopDistancePrice / tickSize; // can be large
   if (ticksAtStop <= 0.0) return 0.0;

   double perLotRisk = ticksAtStop * tickValue; // money per lot if SL hit
   if (perLotRisk <= 0.0) return 0.0;

   double lots = riskMoney / perLotRisk;
   return NormalizeLot(lots);
}

// =============================
// Trade execution
// =============================
bool OpenTrade(int direction)
{
   // direction: 1=buy, -1=sell
   double atrH1 = GetATR_H1(0);
   if (atrH1 <= 0.0) return false;

   double price = 0.0, sl = 0.0;
   double trailBase = atrH1 * ATR_Multiplier_ISL;

   if (direction > 0)
   {
      price = Ask;
      sl    = price - trailBase;
   }
   else
   {
      price = Bid;
      sl    = price + trailBase;
   }

   // Respect broker stop levels
   int stopLevel = GetStopLevelPoints();
   double minStopDist = stopLevel * GetPoint();
   if (direction > 0)
   {
      if ((price - sl) < minStopDist) sl = price - minStopDist;
   }
   else
   {
      if ((sl - price) < minStopDist) sl = price + minStopDist;
   }

   double lots = ComputeLotsByRisk(MathAbs(price - sl));
   if (lots <= 0.0) return false;

   int ticket = -1;
   if (direction > 0)
      ticket = OrderSend(Symbol(), OP_BUY, lots, Ask, Slippage, sl, 0.0, "TrendFollowingEA Buy", MagicNumber, 0, clrBlue);
   else
      ticket = OrderSend(Symbol(), OP_SELL, lots, Bid, Slippage, sl, 0.0, "TrendFollowingEA Sell", MagicNumber, 0, clrRed);

   return (ticket > 0);
}

void UpdateTrailingStops()
{
   double atrH1 = GetATR_H1(0);
   if (atrH1 <= 0.0) return;

   double activateDistance = atrH1; // activate when profit >= 1x ATR(H1)

   for (int i=0; i<OrdersTotal(); i++)
   {
     if (!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
     if (OrderSymbol() != Symbol() || OrderMagicNumber() != MagicNumber) continue;

     int type = OrderType();
     double openPrice = OrderOpenPrice();
     double currentProfitDistance = 0.0;

     double trailMult = ATR_Multiplier_Trail; // default

     if (type == OP_BUY)
     {
        currentProfitDistance = Bid - openPrice;
        if (currentProfitDistance >= 3.0 * atrH1 && Use_Aggressive_Trail) trailMult = MathMin(trailMult, 0.5);
        if (currentProfitDistance >= activateDistance)
        {
           double newSL = Bid - trailMult * atrH1;
           // only move SL up
           if (OrderStopLoss() < newSL)
           {
              // Respect stop level
              int stopLevel = GetStopLevelPoints();
              double minStopDist = stopLevel * GetPoint();
              if ((Bid - newSL) < minStopDist) newSL = Bid - minStopDist;
              newSL = NormalizeDouble(newSL, Digits);
              OrderModify(OrderTicket(), OrderOpenPrice(), newSL, 0.0, 0, clrBlue);
           }
        }
     }
     else if (type == OP_SELL)
     {
        currentProfitDistance = openPrice - Ask;
        if (currentProfitDistance >= 3.0 * atrH1 && Use_Aggressive_Trail) trailMult = MathMin(trailMult, 0.5);
        if (currentProfitDistance >= activateDistance)
        {
           double newSL = Ask + trailMult * atrH1;
           // only move SL down
           if (OrderStopLoss() == 0.0 || OrderStopLoss() > newSL)
           {
              int stopLevel = GetStopLevelPoints();
              double minStopDist = stopLevel * GetPoint();
              if ((newSL - Ask) < minStopDist) newSL = Ask + minStopDist;
              newSL = NormalizeDouble(newSL, Digits);
              OrderModify(OrderTicket(), OrderOpenPrice(), newSL, 0.0, 0, clrRed);
           }
        }
     }
   }
}

// =============================
// Circuit breaker
// =============================
void UpdateCircuitBreaker()
{
   double eq = AccountEquity();
   if (eq > g_peakEquity) g_peakEquity = eq;

   double threshold = g_peakEquity * (1.0 - Max_Drawdown_Percent/100.0);
   if (eq <= threshold)
   {
      g_circuitTripped = true;
      CloseAllPositions();
   }
}

// =============================
// Main event handlers
// =============================
int OnInit()
{
   g_peakEquity = AccountEquity();
   g_circuitTripped = false;
   g_lastProcessedM15BarTime = 0;
   return(INIT_SUCCEEDED);
}

void OnDeinit()
{
}

void OnTick()
{
   // Maintain peak equity and enforce circuit breaker
   UpdateCircuitBreaker();

   // Always manage trailing stops for existing position
   UpdateTrailingStops();

   // Enforce one position at a time
   if (HasOpenPosition())
      return;

   // If circuit breaker tripped, do not open new trades
   if (g_circuitTripped)
      return;

   // Process entry only once per closed M15 bar
   datetime m15Bar1Time = iTime(Symbol(), PERIOD_M15, 1);
   if (m15Bar1Time == 0) return; // not enough bars
   if (m15Bar1Time == g_lastProcessedM15BarTime)
      return; // already processed this bar

   // Compute H1 bias
   int bias = GetH1TrendBias();
   if (bias == 0)
   {
      g_lastProcessedM15BarTime = m15Bar1Time; // mark processed to avoid repeated checks within same bar
      return;
   }

   // Check M15 confirmations
   bool maOk   = CheckM15MAConfirmations(bias);
   bool macdOk = CheckM15MACDConfirmations(bias);
   bool rsiOk  = CheckM15RSIConfirmations(bias);

   if (maOk && macdOk && rsiOk)
   {
      // Place trade aligned with bias
      OpenTrade(bias);
   }

   // Mark this bar processed regardless to avoid multiple sends
   g_lastProcessedM15BarTime = m15Bar1Time;
}
