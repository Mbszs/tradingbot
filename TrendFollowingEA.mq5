//+------------------------------------------------------------------+
//|                                           TrendFollowingEA.mq5   |
//|                                 Aggressive Trend Following Bot   |
//|                                    Gold/XAUUSD Optimized         |
//+------------------------------------------------------------------+
#property copyright "TrendFollowing EA 2025"
#property link      ""
#property version   "1.01"
#property strict
#property description "Fixed: Zero trades issue - RSI now uses relaxed momentum mode"
#property description "Added: Debug logging system for troubleshooting"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

//+------------------------------------------------------------------+
//| Input Parameters                                                  |
//+------------------------------------------------------------------+

// === H1 Trend Setup ===
input group "=== H1 Trend Setup ==="
input int MA_Period_1 = 8;          // Fast EMA Period
input int MA_Period_2 = 21;         // Medium EMA Period
input int MA_Period_3 = 34;         // Slow EMA Period
input int MA_Period_4 = 55;         // Slowest EMA Period (Trend Filter)

// === M15 Entry Setup ===
input group "=== M15 Entry Setup ==="
input int M15_MA_Period = 21;       // M15 EMA Period for Entry
input bool Use_MACD_Confirmation = true;  // Use MACD Confirmation
input int MACD_Fast = 12;           // MACD Fast Period
input int MACD_Slow = 26;           // MACD Slow Period
input int MACD_Signal = 9;          // MACD Signal Period
input bool Use_RSI_Confirmation = true;   // Use RSI Confirmation
input int RSI_Period = 14;          // RSI Period
input double RSI_Level = 50.0;      // RSI Level for Momentum
input bool Strict_RSI_Cross = false; // Require exact RSI crossover (strict)

// === Risk Management ===
input group "=== Risk Management ==="
input double Risk_Per_Trade = 0.5;  // Risk % per trade (0.5 = 0.5%)
input int ATR_Period = 14;          // ATR Period
input double ATR_Multiplier_ISL = 2.0;  // ATR Multiplier for Initial Stop Loss
input double ATR_Multiplier_Trail = 1.0; // ATR Multiplier for Trailing Stop
input double ATR_Profit_Activation = 1.0; // ATR profit to activate trailing stop
input bool Use_Aggressive_Trail = true;   // Tighten trail on big profits
input double ATR_Aggressive_Threshold = 3.0; // ATR profit for aggressive trail
input double ATR_Aggressive_Multiplier = 0.5; // Aggressive trail multiplier

// === Circuit Breaker ===
input group "=== Circuit Breaker ==="
input double Max_Drawdown_Percent = 10.0; // Max Drawdown % before shutdown
input bool Enable_Circuit_Breaker = true;  // Enable Circuit Breaker

// === General Settings ===
input group "=== General Settings ==="
input int Magic_Number = 20251030;  // Magic Number
input string Trade_Comment = "TrendFollowEA"; // Trade Comment
input int Slippage = 10;            // Slippage in points
input bool Enable_Debug_Logging = true; // Enable detailed debug logs

//+------------------------------------------------------------------+
//| Global Variables                                                  |
//+------------------------------------------------------------------+
CTrade trade;
CPositionInfo positionInfo;
CAccountInfo accountInfo;

double peakEquity = 0.0;            // Track peak equity for drawdown
bool circuitBreakerTriggered = false; // Circuit breaker status
datetime lastBarTime = 0;           // For new bar detection

// Indicator handles (H1)
int h1_ema8_handle;
int h1_ema21_handle;
int h1_ema34_handle;
int h1_ema55_handle;
int h1_atr_handle;

// Indicator handles (M15)
int m15_ema8_handle;
int m15_ema21_handle;
int m15_ema34_handle;
int m15_macd_handle;
int m15_rsi_handle;

//+------------------------------------------------------------------+
//| Expert initialization function                                    |
//+------------------------------------------------------------------+
int OnInit()
{
    // Set trade parameters
    trade.SetExpertMagicNumber(Magic_Number);
    trade.SetDeviationInPoints(Slippage);
    trade.SetTypeFilling(ORDER_FILLING_FOK);
    trade.SetAsyncMode(false);
    
    // Initialize peak equity
    peakEquity = accountInfo.Equity();
    
    // Create H1 indicator handles
    h1_ema8_handle = iMA(_Symbol, PERIOD_H1, MA_Period_1, 0, MODE_EMA, PRICE_CLOSE);
    h1_ema21_handle = iMA(_Symbol, PERIOD_H1, MA_Period_2, 0, MODE_EMA, PRICE_CLOSE);
    h1_ema34_handle = iMA(_Symbol, PERIOD_H1, MA_Period_3, 0, MODE_EMA, PRICE_CLOSE);
    h1_ema55_handle = iMA(_Symbol, PERIOD_H1, MA_Period_4, 0, MODE_EMA, PRICE_CLOSE);
    h1_atr_handle = iATR(_Symbol, PERIOD_H1, ATR_Period);
    
    // Create M15 indicator handles
    m15_ema8_handle = iMA(_Symbol, PERIOD_M15, MA_Period_1, 0, MODE_EMA, PRICE_CLOSE);
    m15_ema21_handle = iMA(_Symbol, PERIOD_M15, M15_MA_Period, 0, MODE_EMA, PRICE_CLOSE);
    m15_ema34_handle = iMA(_Symbol, PERIOD_M15, MA_Period_3, 0, MODE_EMA, PRICE_CLOSE);
    m15_macd_handle = iMACD(_Symbol, PERIOD_M15, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE);
    m15_rsi_handle = iRSI(_Symbol, PERIOD_M15, RSI_Period, PRICE_CLOSE);
    
    // Validate handles
    if(h1_ema8_handle == INVALID_HANDLE || h1_ema21_handle == INVALID_HANDLE ||
       h1_ema34_handle == INVALID_HANDLE || h1_ema55_handle == INVALID_HANDLE ||
       h1_atr_handle == INVALID_HANDLE || m15_ema8_handle == INVALID_HANDLE ||
       m15_ema21_handle == INVALID_HANDLE || m15_ema34_handle == INVALID_HANDLE ||
       m15_macd_handle == INVALID_HANDLE || m15_rsi_handle == INVALID_HANDLE)
    {
        Print("ERROR: Failed to create indicator handles!");
        return(INIT_FAILED);
    }
    
    Print("TrendFollowing EA initialized successfully");
    Print("Risk per trade: ", Risk_Per_Trade, "%");
    Print("Max Drawdown: ", Max_Drawdown_Percent, "%");
    
    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    // Release indicator handles
    IndicatorRelease(h1_ema8_handle);
    IndicatorRelease(h1_ema21_handle);
    IndicatorRelease(h1_ema34_handle);
    IndicatorRelease(h1_ema55_handle);
    IndicatorRelease(h1_atr_handle);
    IndicatorRelease(m15_ema8_handle);
    IndicatorRelease(m15_ema21_handle);
    IndicatorRelease(m15_ema34_handle);
    IndicatorRelease(m15_macd_handle);
    IndicatorRelease(m15_rsi_handle);
    
    Print("TrendFollowing EA deinitialized. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
{
    // Check for new M15 bar
    if(!IsNewBar())
        return;
    
    // Check circuit breaker
    if(Enable_Circuit_Breaker)
    {
        CheckCircuitBreaker();
        if(circuitBreakerTriggered)
        {
            Print("CIRCUIT BREAKER ACTIVE - No new trades allowed");
            return;
        }
    }
    
    // Manage existing positions (trailing stop)
    ManageOpenPositions();
    
    // Check if we already have an open position (one trade at a time rule)
    if(HasOpenPosition())
        return;
    
    // Analyze market and execute trades
    AnalyzeAndTrade();
}

//+------------------------------------------------------------------+
//| Check if new bar formed on M15                                    |
//+------------------------------------------------------------------+
bool IsNewBar()
{
    datetime currentBarTime = iTime(_Symbol, PERIOD_M15, 0);
    if(currentBarTime != lastBarTime)
    {
        lastBarTime = currentBarTime;
        return true;
    }
    return false;
}

//+------------------------------------------------------------------+
//| Check Circuit Breaker (Max Drawdown)                             |
//+------------------------------------------------------------------+
void CheckCircuitBreaker()
{
    double currentEquity = accountInfo.Equity();
    
    // Update peak equity
    if(currentEquity > peakEquity)
        peakEquity = currentEquity;
    
    // Calculate drawdown from peak
    double drawdownPercent = ((peakEquity - currentEquity) / peakEquity) * 100.0;
    
    if(drawdownPercent >= Max_Drawdown_Percent)
    {
        if(!circuitBreakerTriggered)
        {
            Print("!!! CIRCUIT BREAKER TRIGGERED !!!");
            Print("Drawdown: ", DoubleToString(drawdownPercent, 2), "%");
            Print("Peak Equity: ", peakEquity, " Current Equity: ", currentEquity);
            
            // Close all positions
            CloseAllPositions();
            circuitBreakerTriggered = true;
        }
    }
}

//+------------------------------------------------------------------+
//| Check if we have an open position                                |
//+------------------------------------------------------------------+
bool HasOpenPosition()
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if(positionInfo.SelectByIndex(i))
        {
            if(positionInfo.Symbol() == _Symbol && positionInfo.Magic() == Magic_Number)
                return true;
        }
    }
    return false;
}

//+------------------------------------------------------------------+
//| Close all positions (for circuit breaker)                        |
//+------------------------------------------------------------------+
void CloseAllPositions()
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if(positionInfo.SelectByIndex(i))
        {
            if(positionInfo.Symbol() == _Symbol && positionInfo.Magic() == Magic_Number)
            {
                trade.PositionClose(positionInfo.Ticket());
                Print("Position closed by circuit breaker: ", positionInfo.Ticket());
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Get H1 Trend Bias                                                 |
//| Returns: 1 = Bullish, -1 = Bearish, 0 = No clear trend          |
//+------------------------------------------------------------------+
int GetH1TrendBias()
{
    double ema8[], ema21[], ema34[], ema55[], close[];
    ArraySetAsSeries(ema8, true);
    ArraySetAsSeries(ema21, true);
    ArraySetAsSeries(ema34, true);
    ArraySetAsSeries(ema55, true);
    ArraySetAsSeries(close, true);
    
    // Copy indicator values
    if(CopyBuffer(h1_ema8_handle, 0, 0, 3, ema8) <= 0) return 0;
    if(CopyBuffer(h1_ema21_handle, 0, 0, 3, ema21) <= 0) return 0;
    if(CopyBuffer(h1_ema34_handle, 0, 0, 3, ema34) <= 0) return 0;
    if(CopyBuffer(h1_ema55_handle, 0, 0, 3, ema55) <= 0) return 0;
    if(CopyClose(_Symbol, PERIOD_H1, 0, 3, close) <= 0) return 0;
    
    // Check bullish alignment: Price > 55 EMA AND 8 > 21 > 34 > 55
    if(close[0] > ema55[0] && ema8[0] > ema21[0] && ema21[0] > ema34[0] && ema34[0] > ema55[0])
    {
        return 1; // Bullish bias
    }
    
    // Check bearish alignment: Price < 55 EMA AND 8 < 21 < 34 < 55
    if(close[0] < ema55[0] && ema8[0] < ema21[0] && ema21[0] < ema34[0] && ema34[0] < ema55[0])
    {
        return -1; // Bearish bias
    }
    
    return 0; // No clear trend
}

//+------------------------------------------------------------------+
//| Check M15 Buy Entry Conditions                                    |
//+------------------------------------------------------------------+
bool CheckM15BuyEntry()
{
    double ema8[], ema21[], ema34[], close[];
    ArraySetAsSeries(ema8, true);
    ArraySetAsSeries(ema21, true);
    ArraySetAsSeries(ema34, true);
    ArraySetAsSeries(close, true);
    
    // Copy M15 EMA values
    if(CopyBuffer(m15_ema8_handle, 0, 0, 3, ema8) <= 0) return false;
    if(CopyBuffer(m15_ema21_handle, 0, 0, 3, ema21) <= 0) return false;
    if(CopyBuffer(m15_ema34_handle, 0, 0, 3, ema34) <= 0) return false;
    if(CopyClose(_Symbol, PERIOD_M15, 0, 3, close) <= 0) return false;
    
    // Condition 1: Price closed above 21 EMA AND EMA alignment (8 > 21 > 34)
    bool priceAbove21 = close[1] > ema21[1];
    bool emaAlignment = (ema8[0] > ema21[0]) && (ema21[0] > ema34[0]);
    bool maCondition = priceAbove21 && emaAlignment;
    
    if(Enable_Debug_Logging)
    {
        Print("[DEBUG BUY] MA Condition: ", maCondition ? "PASS" : "FAIL");
        Print("[DEBUG BUY]   - Price[1] vs EMA21[1]: ", close[1], " vs ", ema21[1], " = ", priceAbove21 ? "ABOVE" : "BELOW");
        Print("[DEBUG BUY]   - EMA Alignment (8>21>34): ", emaAlignment ? "YES" : "NO");
    }
    
    if(!maCondition)
        return false;
    
    // Condition 2: MACD Confirmation
    if(Use_MACD_Confirmation)
    {
        double macdMain[], macdSignal[];
        ArraySetAsSeries(macdMain, true);
        ArraySetAsSeries(macdSignal, true);
        
        if(CopyBuffer(m15_macd_handle, 0, 0, 3, macdMain) <= 0) return false;
        if(CopyBuffer(m15_macd_handle, 1, 0, 3, macdSignal) <= 0) return false;
        
        double histogram0 = macdMain[0] - macdSignal[0];
        double histogram1 = macdMain[1] - macdSignal[1];
        
        bool macdAboveZero = histogram0 > 0;
        bool macdAccelerating = histogram0 > histogram1;
        bool macdCondition = macdAboveZero && macdAccelerating;
        
        if(Enable_Debug_Logging)
        {
            Print("[DEBUG BUY] MACD Condition: ", macdCondition ? "PASS" : "FAIL");
            Print("[DEBUG BUY]   - Histogram: ", histogram0, " (prev: ", histogram1, ")");
            Print("[DEBUG BUY]   - Above zero: ", macdAboveZero ? "YES" : "NO", " | Accelerating: ", macdAccelerating ? "YES" : "NO");
        }
        
        // Histogram above zero and accelerating
        if(!macdCondition)
            return false;
    }
    
    // Condition 3: RSI Momentum
    if(Use_RSI_Confirmation)
    {
        double rsi[];
        ArraySetAsSeries(rsi, true);
        
        if(CopyBuffer(m15_rsi_handle, 0, 0, 3, rsi) <= 0) return false;
        
        bool rsiCondition = false;
        
        // RSI momentum check
        if(Strict_RSI_Cross)
        {
            // Strict: RSI crosses above 50 from below on current bar
            rsiCondition = (rsi[0] > RSI_Level && rsi[1] <= RSI_Level);
            if(Enable_Debug_Logging)
            {
                Print("[DEBUG BUY] RSI Condition (STRICT): ", rsiCondition ? "PASS" : "FAIL");
                Print("[DEBUG BUY]   - RSI[0]: ", rsi[0], " | RSI[1]: ", rsi[1], " | Level: ", RSI_Level);
                Print("[DEBUG BUY]   - Cross from below required");
            }
        }
        else
        {
            // Relaxed: RSI above 50 and rising (building momentum)
            rsiCondition = (rsi[0] > RSI_Level && rsi[0] > rsi[1]);
            if(Enable_Debug_Logging)
            {
                Print("[DEBUG BUY] RSI Condition (RELAXED): ", rsiCondition ? "PASS" : "FAIL");
                Print("[DEBUG BUY]   - RSI[0]: ", rsi[0], " | RSI[1]: ", rsi[1], " | Level: ", RSI_Level);
                Print("[DEBUG BUY]   - Above ", RSI_Level, ": ", rsi[0] > RSI_Level ? "YES" : "NO", " | Rising: ", rsi[0] > rsi[1] ? "YES" : "NO");
            }
        }
        
        if(!rsiCondition)
            return false;
    }
    
    if(Enable_Debug_Logging)
        Print("[DEBUG BUY] *** ALL CONDITIONS PASSED - BUY SIGNAL VALID ***");
    
    return true;
}

//+------------------------------------------------------------------+
//| Check M15 Sell Entry Conditions                                   |
//+------------------------------------------------------------------+
bool CheckM15SellEntry()
{
    double ema8[], ema21[], ema34[], close[];
    ArraySetAsSeries(ema8, true);
    ArraySetAsSeries(ema21, true);
    ArraySetAsSeries(ema34, true);
    ArraySetAsSeries(close, true);
    
    // Copy M15 EMA values
    if(CopyBuffer(m15_ema8_handle, 0, 0, 3, ema8) <= 0) return false;
    if(CopyBuffer(m15_ema21_handle, 0, 0, 3, ema21) <= 0) return false;
    if(CopyBuffer(m15_ema34_handle, 0, 0, 3, ema34) <= 0) return false;
    if(CopyClose(_Symbol, PERIOD_M15, 0, 3, close) <= 0) return false;
    
    // Condition 1: Price closed below 21 EMA AND EMA alignment (8 < 21 < 34)
    bool priceBelow21 = close[1] < ema21[1];
    bool emaAlignment = (ema8[0] < ema21[0]) && (ema21[0] < ema34[0]);
    bool maCondition = priceBelow21 && emaAlignment;
    
    if(Enable_Debug_Logging)
    {
        Print("[DEBUG SELL] MA Condition: ", maCondition ? "PASS" : "FAIL");
        Print("[DEBUG SELL]   - Price[1] vs EMA21[1]: ", close[1], " vs ", ema21[1], " = ", priceBelow21 ? "BELOW" : "ABOVE");
        Print("[DEBUG SELL]   - EMA Alignment (8<21<34): ", emaAlignment ? "YES" : "NO");
    }
    
    if(!maCondition)
        return false;
    
    // Condition 2: MACD Confirmation
    if(Use_MACD_Confirmation)
    {
        double macdMain[], macdSignal[];
        ArraySetAsSeries(macdMain, true);
        ArraySetAsSeries(macdSignal, true);
        
        if(CopyBuffer(m15_macd_handle, 0, 0, 3, macdMain) <= 0) return false;
        if(CopyBuffer(m15_macd_handle, 1, 0, 3, macdSignal) <= 0) return false;
        
        double histogram0 = macdMain[0] - macdSignal[0];
        double histogram1 = macdMain[1] - macdSignal[1];
        
        bool macdBelowZero = histogram0 < 0;
        bool macdAccelerating = histogram0 < histogram1;
        bool macdCondition = macdBelowZero && macdAccelerating;
        
        if(Enable_Debug_Logging)
        {
            Print("[DEBUG SELL] MACD Condition: ", macdCondition ? "PASS" : "FAIL");
            Print("[DEBUG SELL]   - Histogram: ", histogram0, " (prev: ", histogram1, ")");
            Print("[DEBUG SELL]   - Below zero: ", macdBelowZero ? "YES" : "NO", " | Accelerating: ", macdAccelerating ? "YES" : "NO");
        }
        
        // Histogram below zero and accelerating
        if(!macdCondition)
            return false;
    }
    
    // Condition 3: RSI Momentum
    if(Use_RSI_Confirmation)
    {
        double rsi[];
        ArraySetAsSeries(rsi, true);
        
        if(CopyBuffer(m15_rsi_handle, 0, 0, 3, rsi) <= 0) return false;
        
        bool rsiCondition = false;
        
        // RSI momentum check
        if(Strict_RSI_Cross)
        {
            // Strict: RSI crosses below 50 from above on current bar
            rsiCondition = (rsi[0] < RSI_Level && rsi[1] >= RSI_Level);
            if(Enable_Debug_Logging)
            {
                Print("[DEBUG SELL] RSI Condition (STRICT): ", rsiCondition ? "PASS" : "FAIL");
                Print("[DEBUG SELL]   - RSI[0]: ", rsi[0], " | RSI[1]: ", rsi[1], " | Level: ", RSI_Level);
                Print("[DEBUG SELL]   - Cross from above required");
            }
        }
        else
        {
            // Relaxed: RSI below 50 and falling (building momentum)
            rsiCondition = (rsi[0] < RSI_Level && rsi[0] < rsi[1]);
            if(Enable_Debug_Logging)
            {
                Print("[DEBUG SELL] RSI Condition (RELAXED): ", rsiCondition ? "PASS" : "FAIL");
                Print("[DEBUG SELL]   - RSI[0]: ", rsi[0], " | RSI[1]: ", rsi[1], " | Level: ", RSI_Level);
                Print("[DEBUG SELL]   - Below ", RSI_Level, ": ", rsi[0] < RSI_Level ? "YES" : "NO", " | Falling: ", rsi[0] < rsi[1] ? "YES" : "NO");
            }
        }
        
        if(!rsiCondition)
            return false;
    }
    
    if(Enable_Debug_Logging)
        Print("[DEBUG SELL] *** ALL CONDITIONS PASSED - SELL SIGNAL VALID ***");
    
    return true;
}

//+------------------------------------------------------------------+
//| Get H1 ATR value                                                  |
//+------------------------------------------------------------------+
double GetH1ATR()
{
    double atr[];
    ArraySetAsSeries(atr, true);
    
    if(CopyBuffer(h1_atr_handle, 0, 0, 2, atr) <= 0)
        return 0;
    
    return atr[0];
}

//+------------------------------------------------------------------+
//| Calculate position size based on risk                            |
//+------------------------------------------------------------------+
double CalculatePositionSize(double stopLossDistance)
{
    if(stopLossDistance <= 0)
        return 0;
    
    double accountBalance = accountInfo.Balance();
    double riskAmount = accountBalance * (Risk_Per_Trade / 100.0);
    
    double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
    double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
    double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
    double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
    double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
    
    // Calculate lot size
    double lots = (riskAmount / (stopLossDistance / tickSize * tickValue));
    
    // Normalize to lot step
    lots = MathFloor(lots / lotStep) * lotStep;
    
    // Ensure within min/max bounds
    if(lots < minLot) lots = minLot;
    if(lots > maxLot) lots = maxLot;
    
    return lots;
}

//+------------------------------------------------------------------+
//| Analyze market and execute trades                                |
//+------------------------------------------------------------------+
void AnalyzeAndTrade()
{
    // Step 1: Get H1 Trend Bias
    int trendBias = GetH1TrendBias();
    
    if(Enable_Debug_Logging)
    {
        string biasStr = (trendBias == 1) ? "BULLISH" : (trendBias == -1) ? "BEARISH" : "NEUTRAL";
        Print("[DEBUG] H1 Trend Bias: ", biasStr);
    }
    
    if(trendBias == 0)
    {
        if(Enable_Debug_Logging)
            Print("[DEBUG] No clear H1 trend - waiting for alignment");
        return; // No clear trend
    }
    
    // Step 2: Get H1 ATR for stop loss calculation
    double atr = GetH1ATR();
    if(atr <= 0)
    {
        Print("ERROR: Invalid ATR value");
        return;
    }
    
    double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    
    // Step 3: Check for Buy Entry
    if(trendBias == 1)
    {
        bool buySignal = CheckM15BuyEntry();
        if(Enable_Debug_Logging)
            Print("[DEBUG] M15 Buy Entry Check: ", buySignal ? "PASSED" : "FAILED");
        
        if(buySignal)
    {
        double sl = bid - (ATR_Multiplier_ISL * atr);
        double slDistance = bid - sl;
        double lotSize = CalculatePositionSize(slDistance);
        
        if(lotSize > 0)
        {
            Print("=== BUY SIGNAL ===");
            Print("Entry: ", ask, " | SL: ", sl, " | Lot: ", lotSize);
            Print("ATR: ", atr, " | SL Distance: ", slDistance);
            
            if(trade.Buy(lotSize, _Symbol, ask, sl, 0, Trade_Comment))
            {
                Print("BUY order executed successfully. Ticket: ", trade.ResultOrder());
            }
            else
            {
                Print("ERROR: Buy order failed. Code: ", trade.ResultRetcode());
            }
        }
        }
    }
    // Step 4: Check for Sell Entry
    else if(trendBias == -1)
    {
        bool sellSignal = CheckM15SellEntry();
        if(Enable_Debug_Logging)
            Print("[DEBUG] M15 Sell Entry Check: ", sellSignal ? "PASSED" : "FAILED");
        
        if(sellSignal)
    {
        double sl = ask + (ATR_Multiplier_ISL * atr);
        double slDistance = sl - ask;
        double lotSize = CalculatePositionSize(slDistance);
        
        if(lotSize > 0)
        {
            Print("=== SELL SIGNAL ===");
            Print("Entry: ", bid, " | SL: ", sl, " | Lot: ", lotSize);
            Print("ATR: ", atr, " | SL Distance: ", slDistance);
            
            if(trade.Sell(lotSize, _Symbol, bid, sl, 0, Trade_Comment))
            {
                Print("SELL order executed successfully. Ticket: ", trade.ResultOrder());
            }
            else
            {
                Print("ERROR: Sell order failed. Code: ", trade.ResultRetcode());
            }
        }
        }
    }
}

//+------------------------------------------------------------------+
//| Manage open positions (Trailing Stop)                            |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if(!positionInfo.SelectByIndex(i))
            continue;
            
        if(positionInfo.Symbol() != _Symbol || positionInfo.Magic() != Magic_Number)
            continue;
        
        // Get current ATR
        double atr = GetH1ATR();
        if(atr <= 0)
            continue;
        
        double positionOpenPrice = positionInfo.PriceOpen();
        double positionCurrentSL = positionInfo.StopLoss();
        double currentPrice = (positionInfo.Type() == POSITION_TYPE_BUY) ? 
                              SymbolInfoDouble(_Symbol, SYMBOL_BID) : 
                              SymbolInfoDouble(_Symbol, SYMBOL_ASK);
        
        // Calculate profit in ATR units
        double profitDistance = 0;
        if(positionInfo.Type() == POSITION_TYPE_BUY)
            profitDistance = currentPrice - positionOpenPrice;
        else
            profitDistance = positionOpenPrice - currentPrice;
        
        double profitInATR = profitDistance / atr;
        
        // Check if profit is enough to activate trailing stop
        if(profitInATR < ATR_Profit_Activation)
            continue;
        
        // Determine trailing stop distance
        double trailMultiplier = ATR_Multiplier_Trail;
        
        // Use aggressive trail if profit is large
        if(Use_Aggressive_Trail && profitInATR >= ATR_Aggressive_Threshold)
        {
            trailMultiplier = ATR_Aggressive_Multiplier;
        }
        
        double newSL = 0;
        
        if(positionInfo.Type() == POSITION_TYPE_BUY)
        {
            // Calculate new trailing stop for buy
            newSL = currentPrice - (trailMultiplier * atr);
            
            // Only move SL up, never down
            if(newSL <= positionCurrentSL)
                continue;
                
            // Ensure SL is below current price
            if(newSL >= currentPrice)
                continue;
        }
        else // SELL
        {
            // Calculate new trailing stop for sell
            newSL = currentPrice + (trailMultiplier * atr);
            
            // Only move SL down, never up
            if(positionCurrentSL > 0 && newSL >= positionCurrentSL)
                continue;
                
            // Ensure SL is above current price
            if(newSL <= currentPrice)
                continue;
        }
        
        // Normalize SL
        double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
        newSL = NormalizeDouble(newSL, (int)MathRound(MathLog10(1.0 / tickSize)));
        
        // Modify stop loss
        if(trade.PositionModify(positionInfo.Ticket(), newSL, 0))
        {
            Print("Trailing stop updated for ticket: ", positionInfo.Ticket());
            Print("New SL: ", newSL, " | Profit in ATR: ", DoubleToString(profitInATR, 2));
            Print("Trail multiplier used: ", trailMultiplier);
        }
        else
        {
            Print("ERROR: Failed to modify position. Code: ", trade.ResultRetcode());
        }
    }
}
//+------------------------------------------------------------------+
