//+------------------------------------------------------------------+
//|                                           TrendFollowingEA.mq5   |
//|                                 Aggressive Trend Following Bot   |
//|                                    Gold/XAUUSD Optimized         |
//+------------------------------------------------------------------+
#property copyright "TrendFollowing EA 2025"
#property link      ""
#property version   "1.02"
#property description "No stop loss - Manual exit only"
#property description "Session filters with strong trend override"
#property description "No circuit breaker - Permanent trading mode"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

//+------------------------------------------------------------------+
//| Input Parameters                                                  |
//+------------------------------------------------------------------+

// === H1 Trend Setup ===
sinput group "=== H1 Trend Setup ==="
input int MA_Period_1 = 8;          // Fast EMA Period
input int MA_Period_2 = 21;         // Medium EMA Period
input int MA_Period_3 = 34;         // Slow EMA Period
input int MA_Period_4 = 55;         // Slowest EMA Period (Trend Filter)

// === M15 Entry Setup ===
sinput group "=== M15 Entry Setup ==="
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
sinput group "=== Risk Management ==="
input double Risk_Per_Trade = 0.5;  // Risk % per trade (0.5 = 0.5%)
input double Fixed_Lot_Size = 0.0;  // Fixed lot size (0 = auto calculate)
input bool Use_Stop_Loss = false;   // Use stop loss (NOT RECOMMENDED)
input int ATR_Period = 14;          // ATR Period
input double ATR_Multiplier_ISL = 2.0;  // ATR Multiplier for Initial Stop Loss (if enabled)
input bool Use_Trailing_Stop = false; // Use trailing stop
input double ATR_Multiplier_Trail = 1.0; // ATR Multiplier for Trailing Stop
input double ATR_Profit_Activation = 1.0; // ATR profit to activate trailing stop
input bool Use_Aggressive_Trail = false; // Tighten trail on big profits
input double ATR_Aggressive_Threshold = 3.0; // ATR profit for aggressive trail
input double ATR_Aggressive_Multiplier = 0.5; // Aggressive trail multiplier

// === Exit Management ===
sinput group "=== Exit Management ==="
input bool Exit_On_Opposite_Signal = true;  // Close on opposite entry signal
input bool Exit_On_EMA_Cross = true;        // Close when price crosses 21 EMA opposite
input bool Exit_On_Trend_Change = false;    // Close when H1 trend changes

// === Trading Sessions ===
sinput group "=== Trading Sessions ==="
input bool Use_Session_Filter = true;       // Enable session filter
input bool Trade_Asian_Session = false;     // Trade Asian session (00:00-09:00 GMT)
input bool Trade_London_Session = true;     // Trade London session (08:00-17:00 GMT)
input bool Trade_NewYork_Session = true;    // Trade New York session (13:00-22:00 GMT)
input bool Override_On_Strong_Trend = true; // Trade anytime if strong trend detected
input double Strong_Trend_ADX_Level = 25.0; // ADX level for strong trend

// Circuit Breaker REMOVED - Trades permanently with no limits

// === General Settings ===
sinput group "=== General Settings ==="
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

// Indicator handles (H1)
int h1_adx_handle;

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
    
    // No circuit breaker - permanent trading mode
    
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
    h1_adx_handle = iADX(_Symbol, PERIOD_H1, 14);
    
    // Validate handles
    if(h1_ema8_handle == INVALID_HANDLE || h1_ema21_handle == INVALID_HANDLE ||
       h1_ema34_handle == INVALID_HANDLE || h1_ema55_handle == INVALID_HANDLE ||
       h1_atr_handle == INVALID_HANDLE || h1_adx_handle == INVALID_HANDLE ||
       m15_ema8_handle == INVALID_HANDLE || m15_ema21_handle == INVALID_HANDLE ||
       m15_ema34_handle == INVALID_HANDLE || m15_macd_handle == INVALID_HANDLE ||
       m15_rsi_handle == INVALID_HANDLE)
    {
        Print("ERROR: Failed to create indicator handles!");
        return(INIT_FAILED);
    }
    
    Print("TrendFollowing EA v1.02 initialized successfully");
    Print("Mode: NO STOP LOSS - Manual exits only");
    Print("Session Filter: ", Use_Session_Filter ? "ENABLED" : "DISABLED");
    Print("Circuit Breaker: REMOVED - Permanent trading mode");
    Print("WARNING: No drawdown protection - EA will trade indefinitely");
    if(Fixed_Lot_Size > 0)
        Print("Using fixed lot size: ", Fixed_Lot_Size);
    else
        Print("Using calculated lot size: ", Risk_Per_Trade, "% risk per trade");
    
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
    IndicatorRelease(h1_adx_handle);
    
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
    
    // Circuit breaker removed - trades permanently
    
    // Check for manual exit conditions on existing positions
    CheckManualExits();
    
    // Manage existing positions (trailing stop if enabled)
    if(Use_Trailing_Stop)
        ManageOpenPositions();
    
    // Check if we already have an open position (one trade at a time rule)
    if(HasOpenPosition())
        return;
    
    // Check if we can trade (session filter)
    if(!CanTradeNow())
    {
        if(Enable_Debug_Logging)
            Print("[DEBUG] Outside trading session - waiting");
        return;
    }
    
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

// Circuit breaker function removed - EA trades permanently with no limits

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

// CloseAllPositions function removed - only manual exits used

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
//| Check if strong trend exists (for session override)              |
//+------------------------------------------------------------------+
bool IsStrongTrend()
{
    if(!Override_On_Strong_Trend)
        return false;
    
    double adx[];
    ArraySetAsSeries(adx, true);
    
    // ADX main line is buffer 0
    if(CopyBuffer(h1_adx_handle, 0, 0, 2, adx) <= 0)
        return false;
    
    bool strongTrend = adx[0] >= Strong_Trend_ADX_Level;
    
    if(Enable_Debug_Logging && strongTrend)
        Print("[DEBUG] Strong trend detected: ADX = ", adx[0]);
    
    return strongTrend;
}

//+------------------------------------------------------------------+
//| Check if we can trade based on session                           |
//+------------------------------------------------------------------+
bool CanTradeNow()
{
    if(!Use_Session_Filter)
        return true;
    
    // Check if strong trend overrides session filter
    if(IsStrongTrend())
    {
        if(Enable_Debug_Logging)
            Print("[DEBUG] Strong trend - session filter bypassed");
        return true;
    }
    
    // Get current GMT time
    datetime currentTime = TimeGMT();
    MqlDateTime dt;
    TimeToStruct(currentTime, dt);
    
    int currentHour = dt.hour;
    
    // Asian Session: 00:00 - 09:00 GMT
    if(Trade_Asian_Session && currentHour >= 0 && currentHour < 9)
        return true;
    
    // London Session: 08:00 - 17:00 GMT
    if(Trade_London_Session && currentHour >= 8 && currentHour < 17)
        return true;
    
    // New York Session: 13:00 - 22:00 GMT
    if(Trade_NewYork_Session && currentHour >= 13 && currentHour < 22)
        return true;
    
    return false;
}

//+------------------------------------------------------------------+
//| Check manual exit conditions                                     |
//+------------------------------------------------------------------+
void CheckManualExits()
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if(!positionInfo.SelectByIndex(i))
            continue;
            
        if(positionInfo.Symbol() != _Symbol || positionInfo.Magic() != Magic_Number)
            continue;
        
        bool shouldExit = false;
        string exitReason = "";
        
        ENUM_POSITION_TYPE posType = positionInfo.Type();
        
        // Exit on opposite signal
        if(Exit_On_Opposite_Signal)
        {
            if(posType == POSITION_TYPE_BUY && CheckM15SellEntry())
            {
                shouldExit = true;
                exitReason = "Opposite SELL signal detected";
            }
            else if(posType == POSITION_TYPE_SELL && CheckM15BuyEntry())
            {
                shouldExit = true;
                exitReason = "Opposite BUY signal detected";
            }
        }
        
        // Exit on EMA cross
        if(Exit_On_EMA_Cross && !shouldExit)
        {
            double ema21[], close[];
            ArraySetAsSeries(ema21, true);
            ArraySetAsSeries(close, true);
            
            if(CopyBuffer(m15_ema21_handle, 0, 0, 3, ema21) > 0 &&
               CopyClose(_Symbol, PERIOD_M15, 0, 3, close) > 0)
            {
                if(posType == POSITION_TYPE_BUY && close[0] < ema21[0] && close[1] >= ema21[1])
                {
                    shouldExit = true;
                    exitReason = "Price crossed below 21 EMA";
                }
                else if(posType == POSITION_TYPE_SELL && close[0] > ema21[0] && close[1] <= ema21[1])
                {
                    shouldExit = true;
                    exitReason = "Price crossed above 21 EMA";
                }
            }
        }
        
        // Exit on H1 trend change
        if(Exit_On_Trend_Change && !shouldExit)
        {
            int currentTrendBias = GetH1TrendBias();
            
            if(posType == POSITION_TYPE_BUY && currentTrendBias == -1)
            {
                shouldExit = true;
                exitReason = "H1 trend changed to BEARISH";
            }
            else if(posType == POSITION_TYPE_SELL && currentTrendBias == 1)
            {
                shouldExit = true;
                exitReason = "H1 trend changed to BULLISH";
            }
        }
        
        // Execute exit
        if(shouldExit)
        {
            Print("=== MANUAL EXIT ===");
            Print("Reason: ", exitReason);
            Print("Position: ", posType == POSITION_TYPE_BUY ? "BUY" : "SELL");
            Print("Ticket: ", positionInfo.Ticket());
            
            if(trade.PositionClose(positionInfo.Ticket()))
            {
                Print("Position closed successfully");
            }
            else
            {
                Print("ERROR: Failed to close position. Code: ", trade.ResultRetcode());
            }
        }
    }
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
//| Calculate position size                                          |
//| Simple formula: $500 = 0.01 lot, $10,000 = 0.2 lot             |
//+------------------------------------------------------------------+
double CalculatePositionSize()
{
    // Use fixed lot size if specified
    if(Fixed_Lot_Size > 0)
        return Fixed_Lot_Size;
    
    double accountBalance = accountInfo.Balance();
    
    // Simple linear scaling: $500 = 0.01 lot
    // Formula: Lot = Balance / 50000
    double lots = accountBalance / 50000.0;
    
    // Get broker constraints
    double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
    double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
    double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
    
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
        double lotSize = CalculatePositionSize();
        
        if(lotSize > 0)
        {
            double sl = 0;
            double tp = 0;
            
            // Set stop loss only if enabled
            if(Use_Stop_Loss)
            {
                sl = bid - (ATR_Multiplier_ISL * atr);
                Print("=== BUY SIGNAL (WITH SL) ===");
                Print("Entry: ", ask, " | SL: ", sl, " | Lot: ", lotSize);
            }
            else
            {
                Print("=== BUY SIGNAL (NO SL - MANUAL EXIT) ===");
                Print("Entry: ", ask, " | Lot: ", lotSize, " | Manual exit enabled");
            }
            
            Print("ATR: ", atr);
            
            if(trade.Buy(lotSize, _Symbol, ask, sl, tp, Trade_Comment))
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
        double lotSize = CalculatePositionSize();
        
        if(lotSize > 0)
        {
            double sl = 0;
            double tp = 0;
            
            // Set stop loss only if enabled
            if(Use_Stop_Loss)
            {
                sl = ask + (ATR_Multiplier_ISL * atr);
                Print("=== SELL SIGNAL (WITH SL) ===");
                Print("Entry: ", bid, " | SL: ", sl, " | Lot: ", lotSize);
            }
            else
            {
                Print("=== SELL SIGNAL (NO SL - MANUAL EXIT) ===");
                Print("Entry: ", bid, " | Lot: ", lotSize, " | Manual exit enabled");
            }
            
            Print("ATR: ", atr);
            
            if(trade.Sell(lotSize, _Symbol, bid, sl, tp, Trade_Comment))
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
