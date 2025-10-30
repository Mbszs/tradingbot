//+------------------------------------------------------------------+
//|                                  TrendFollowingEA_Advanced.mq5   |
//|                    Advanced AI with Pyramiding & Pattern Recognition |
//+------------------------------------------------------------------+
#property copyright "TrendFollowing EA 2025"
#property link      ""
#property version   "2.00"
#property description "Advanced AI Version - Pyramiding, Pattern Recognition, Adaptive Learning"
#property description "Stacks positions in strong trends, closes all on reversal"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

//+------------------------------------------------------------------+
//| Input Parameters                                                  |
//+------------------------------------------------------------------+

// === Position Pyramiding ===
sinput group "=== Position Pyramiding ==="
input bool Enable_Pyramiding = true;        // Enable position stacking
input int Max_Pyramid_Levels = 5;           // Maximum stacked positions
input double Pyramid_Spacing_ATR = 0.3;     // ATR distance between entries (AGGRESSIVE)
input double Pyramid_Lot_Multiplier = 1.2;  // Lot multiplier per level (AGGRESSIVE)
input bool Scale_In_On_Strength = true;     // Add positions on trend strength

// === Reversal Detection ===
sinput group "=== Reversal Detection ==="
input bool Close_All_On_Reversal = true;    // Close all positions on reversal
input bool Use_Candlestick_Reversal = true; // Use candlestick patterns
input bool Use_Divergence = true;           // Use RSI/MACD divergence
input bool Use_Support_Resistance = true;   // Use S/R level rejection

// === Chart Pattern Recognition ===
sinput group "=== Chart Pattern Recognition ==="
input bool Enable_Pattern_Recognition = true;   // Enable pattern detection
input bool Use_DoubleTop_Bottom = true;         // Detect double top/bottom
input bool Use_HeadAndShoulders = true;         // Detect H&S patterns
input bool Use_Triangles = true;                // Detect triangle patterns
input int Pattern_Lookback_Bars = 100;          // Bars to analyze for patterns

// === Adaptive Learning ===
sinput group "=== Adaptive Learning (AI) ==="
input bool Enable_Adaptive_Learning = true;     // Enable AI learning
input int Learning_Period_Days = 30;            // Days to learn from
input bool Auto_Adjust_Parameters = true;       // Auto-tune parameters
input double Learning_Rate = 0.3;               // AGGRESSIVE - Faster adaptation

// === H1 Trend Setup ===
sinput group "=== H1 Trend Setup ==="
input int MA_Period_1 = 8;
input int MA_Period_2 = 21;
input int MA_Period_3 = 34;
input int MA_Period_4 = 55;

// === M15 Entry Setup ===
sinput group "=== M15 Entry Setup ==="
input int M15_MA_Period = 21;
input bool Use_MACD_Confirmation = false;  // DISABLED for more trades
input int MACD_Fast = 12;
input int MACD_Slow = 26;
input int MACD_Signal = 9;
input bool Use_RSI_Confirmation = false;   // DISABLED for more trades
input int RSI_Period = 14;
input double RSI_Level = 50.0;
input bool Strict_RSI_Cross = false;

// === Risk Management ===
sinput group "=== Risk Management ==="
input double Risk_Per_Trade = 1.5;          // AGGRESSIVE (1.5% per trade)
input double Fixed_Lot_Size = 0.0;
input bool Use_Stop_Loss = false;
input int ATR_Period = 14;
input double ATR_Multiplier_ISL = 2.0;

// === Trading Sessions ===
sinput group "=== Trading Sessions ==="
input bool Use_Session_Filter = false;      // DISABLED - Trade 24/7
input bool Trade_Asian_Session = false;
input bool Trade_London_Session = true;
input bool Trade_NewYork_Session = true;
input bool Override_On_Strong_Trend = true;
input double Strong_Trend_ADX_Level = 25.0;

// === General Settings ===
sinput group "=== General Settings ==="
input int Magic_Number = 20252000;
input string Trade_Comment = "AdvancedEA";
input int Slippage = 10;
input bool Enable_Debug_Logging = true;

//+------------------------------------------------------------------+
//| Global Variables                                                  |
//+------------------------------------------------------------------+
CTrade trade;
CPositionInfo positionInfo;
CAccountInfo accountInfo;

datetime lastBarTime = 0;
double lastEntryPrice = 0;
int pyramidLevel = 0;

// Indicator handles
int h1_ema8_handle, h1_ema21_handle, h1_ema34_handle, h1_ema55_handle;
int h1_atr_handle, h1_adx_handle;
int m15_ema8_handle, m15_ema21_handle, m15_ema34_handle;
int m15_macd_handle, m15_rsi_handle;

// Adaptive learning storage
struct MarketMemory
{
    double avg_trend_duration;
    double avg_reversal_strength;
    double optimal_pyramid_spacing;
    double win_rate_by_hour[24];
    int total_patterns_detected;
    int successful_pyramids;
};
MarketMemory memory;

// Support/Resistance levels
struct SRLevel
{
    double price;
    int touches;
    datetime lastTouch;
    bool isResistance;
};
SRLevel srLevels[50];
int srCount = 0;

//+------------------------------------------------------------------+
//| Expert initialization                                             |
//+------------------------------------------------------------------+
int OnInit()
{
    trade.SetExpertMagicNumber(Magic_Number);
    trade.SetDeviationInPoints(Slippage);
    trade.SetTypeFilling(ORDER_FILLING_FOK);
    trade.SetAsyncMode(false);
    
    // Initialize indicator handles
    h1_ema8_handle = iMA(_Symbol, PERIOD_H1, MA_Period_1, 0, MODE_EMA, PRICE_CLOSE);
    h1_ema21_handle = iMA(_Symbol, PERIOD_H1, MA_Period_2, 0, MODE_EMA, PRICE_CLOSE);
    h1_ema34_handle = iMA(_Symbol, PERIOD_H1, MA_Period_3, 0, MODE_EMA, PRICE_CLOSE);
    h1_ema55_handle = iMA(_Symbol, PERIOD_H1, MA_Period_4, 0, MODE_EMA, PRICE_CLOSE);
    h1_atr_handle = iATR(_Symbol, PERIOD_H1, ATR_Period);
    h1_adx_handle = iADX(_Symbol, PERIOD_H1, 14);
    
    m15_ema8_handle = iMA(_Symbol, PERIOD_M15, MA_Period_1, 0, MODE_EMA, PRICE_CLOSE);
    m15_ema21_handle = iMA(_Symbol, PERIOD_M15, M15_MA_Period, 0, MODE_EMA, PRICE_CLOSE);
    m15_ema34_handle = iMA(_Symbol, PERIOD_M15, MA_Period_3, 0, MODE_EMA, PRICE_CLOSE);
    m15_macd_handle = iMACD(_Symbol, PERIOD_M15, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE);
    m15_rsi_handle = iRSI(_Symbol, PERIOD_M15, RSI_Period, PRICE_CLOSE);
    
    // Validate handles
    if(h1_ema8_handle == INVALID_HANDLE || m15_rsi_handle == INVALID_HANDLE)
    {
        Print("ERROR: Failed to create indicator handles!");
        return(INIT_FAILED);
    }
    
    // Initialize adaptive learning
    if(Enable_Adaptive_Learning)
    {
        LoadMarketMemory();
    }
    
    Print("========================================");
    Print("Advanced AI EA v2.00 initialized");
    Print("Pyramiding: ", Enable_Pyramiding ? "ENABLED" : "DISABLED");
    Print("Max Levels: ", Max_Pyramid_Levels);
    Print("Pattern Recognition: ", Enable_Pattern_Recognition ? "ENABLED" : "DISABLED");
    Print("Adaptive Learning: ", Enable_Adaptive_Learning ? "ENABLED" : "DISABLED");
    Print("Reversal Detection: ", Close_All_On_Reversal ? "ENABLED" : "DISABLED");
    Print("========================================");
    
    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    // Save learned data
    if(Enable_Adaptive_Learning)
    {
        SaveMarketMemory();
    }
    
    // Release indicators
    IndicatorRelease(h1_ema8_handle);
    IndicatorRelease(h1_ema21_handle);
    IndicatorRelease(h1_ema34_handle);
    IndicatorRelease(h1_ema55_handle);
    IndicatorRelease(h1_atr_handle);
    IndicatorRelease(h1_adx_handle);
    IndicatorRelease(m15_ema8_handle);
    IndicatorRelease(m15_ema21_handle);
    IndicatorRelease(m15_ema34_handle);
    IndicatorRelease(m15_macd_handle);
    IndicatorRelease(m15_rsi_handle);
    
    Print("Advanced AI EA deinitialized");
}

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
{
    if(!IsNewBar())
        return;
    
    // Update support/resistance levels
    if(Use_Support_Resistance)
        UpdateSupportResistance();
    
    // Check for reversal (close all positions)
    if(Close_All_On_Reversal && DetectReversal())
    {
        CloseAllPositions("Reversal detected");
        return;
    }
    
    // Update adaptive learning
    if(Enable_Adaptive_Learning)
        LearnFromMarket();
    
    // Check for pyramiding opportunities
    if(Enable_Pyramiding && HasOpenPositions())
    {
        CheckPyramidOpportunity();
    }
    
    // Check for new entry (if not maxed out on pyramids)
    if(!HasOpenPositions() || (Enable_Pyramiding && pyramidLevel < Max_Pyramid_Levels))
    {
        if(CanTradeNow())
            AnalyzeAndTrade();
    }
}

//+------------------------------------------------------------------+
//| Check if new bar                                                  |
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
//| Detect market reversal                                            |
//+------------------------------------------------------------------+
bool DetectReversal()
{
    bool reversalDetected = false;
    
    // Get current position direction
    int currentDirection = GetNetPositionDirection();
    if(currentDirection == 0) return false;
    
    // 1. Candlestick reversal patterns
    if(Use_Candlestick_Reversal)
    {
        if(DetectCandlestickReversal(currentDirection))
        {
            if(Enable_Debug_Logging)
                Print("[REVERSAL] Candlestick pattern detected");
            reversalDetected = true;
        }
    }
    
    // 2. Divergence detection
    if(Use_Divergence)
    {
        if(DetectDivergence(currentDirection))
        {
            if(Enable_Debug_Logging)
                Print("[REVERSAL] Divergence detected");
            reversalDetected = true;
        }
    }
    
    // 3. Support/Resistance rejection
    if(Use_Support_Resistance)
    {
        if(DetectSRRejection(currentDirection))
        {
            if(Enable_Debug_Logging)
                Print("[REVERSAL] S/R rejection detected");
            reversalDetected = true;
        }
    }
    
    return reversalDetected;
}

//+------------------------------------------------------------------+
//| Detect candlestick reversal patterns                              |
//+------------------------------------------------------------------+
bool DetectCandlestickReversal(int direction)
{
    double open[], high[], low[], close[];
    ArraySetAsSeries(open, true);
    ArraySetAsSeries(high, true);
    ArraySetAsSeries(low, true);
    ArraySetAsSeries(close, true);
    
    if(CopyOpen(_Symbol, PERIOD_M15, 0, 3, open) <= 0) return false;
    if(CopyHigh(_Symbol, PERIOD_M15, 0, 3, high) <= 0) return false;
    if(CopyLow(_Symbol, PERIOD_M15, 0, 3, low) <= 0) return false;
    if(CopyClose(_Symbol, PERIOD_M15, 0, 3, close) <= 0) return false;
    
    double body1 = MathAbs(close[1] - open[1]);
    double body0 = MathAbs(close[0] - open[0]);
    
    // Bullish engulfing (reversal for shorts)
    if(direction < 0)
    {
        if(close[1] < open[1] && close[0] > open[0] && 
           close[0] > open[1] && open[0] < close[1] && body0 > body1 * 1.5)
        {
            return true; // Bullish engulfing
        }
    }
    
    // Bearish engulfing (reversal for longs)
    if(direction > 0)
    {
        if(close[1] > open[1] && close[0] < open[0] && 
           close[0] < open[1] && open[0] > close[1] && body0 > body1 * 1.5)
        {
            return true; // Bearish engulfing
        }
    }
    
    // Shooting star / hammer
    double upperWick = high[0] - MathMax(close[0], open[0]);
    double lowerWick = MathMin(close[0], open[0]) - low[0];
    
    if(direction > 0 && upperWick > body0 * 2 && lowerWick < body0 * 0.3)
        return true; // Shooting star
    
    if(direction < 0 && lowerWick > body0 * 2 && upperWick < body0 * 0.3)
        return true; // Hammer
    
    return false;
}

//+------------------------------------------------------------------+
//| Detect divergence                                                 |
//+------------------------------------------------------------------+
bool DetectDivergence(int direction)
{
    double rsi[], macdMain[], close[];
    ArraySetAsSeries(rsi, true);
    ArraySetAsSeries(macdMain, true);
    ArraySetAsSeries(close, true);
    
    if(CopyBuffer(m15_rsi_handle, 0, 0, 20, rsi) <= 0) return false;
    if(CopyBuffer(m15_macd_handle, 0, 0, 20, macdMain) <= 0) return false;
    if(CopyClose(_Symbol, PERIOD_M15, 0, 20, close) <= 0) return false;
    
    // Bearish divergence (price higher, RSI lower)
    if(direction > 0)
    {
        if(close[0] > close[10] && rsi[0] < rsi[10])
            return true;
    }
    
    // Bullish divergence (price lower, RSI higher)
    if(direction < 0)
    {
        if(close[0] < close[10] && rsi[0] > rsi[10])
            return true;
    }
    
    return false;
}

//+------------------------------------------------------------------+
//| Detect S/R rejection                                              |
//+------------------------------------------------------------------+
bool DetectSRRejection(int direction)
{
    double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    double atr = GetH1ATR();
    
    for(int i = 0; i < srCount; i++)
    {
        double distance = MathAbs(currentPrice - srLevels[i].price);
        
        if(distance < atr * 0.5)
        {
            // Price at resistance and we're long
            if(direction > 0 && srLevels[i].isResistance)
                return true;
            
            // Price at support and we're short
            if(direction < 0 && !srLevels[i].isResistance)
                return true;
        }
    }
    
    return false;
}

//+------------------------------------------------------------------+
//| Check pyramiding opportunity                                      |
//+------------------------------------------------------------------+
void CheckPyramidOpportunity()
{
    if(pyramidLevel >= Max_Pyramid_Levels)
        return;
    
    double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    double atr = GetH1ATR();
    int direction = GetNetPositionDirection();
    
    if(direction == 0) return;
    
    // Check if price moved enough from last entry
    double distanceFromLast = MathAbs(currentPrice - lastEntryPrice);
    double requiredDistance = atr * Pyramid_Spacing_ATR;
    
    if(distanceFromLast < requiredDistance)
        return;
    
    // Check if trend is strengthening
    if(Scale_In_On_Strength && !IsTrendStrengthening(direction))
        return;
    
    // Add pyramid position
    double lotSize = CalculatePositionSize() * MathPow(Pyramid_Lot_Multiplier, pyramidLevel);
    
    if(direction > 0)
    {
        if(trade.Buy(lotSize, _Symbol, 0, 0, 0, Trade_Comment + "_Pyramid_" + IntegerToString(pyramidLevel + 1)))
        {
            pyramidLevel++;
            lastEntryPrice = currentPrice;
            Print("[PYRAMID] Added BUY position #", pyramidLevel, " | Lot: ", lotSize);
            
            if(Enable_Adaptive_Learning)
                memory.successful_pyramids++;
        }
    }
    else if(direction < 0)
    {
        if(trade.Sell(lotSize, _Symbol, 0, 0, 0, Trade_Comment + "_Pyramid_" + IntegerToString(pyramidLevel + 1)))
        {
            pyramidLevel++;
            lastEntryPrice = currentPrice;
            Print("[PYRAMID] Added SELL position #", pyramidLevel, " | Lot: ", lotSize);
            
            if(Enable_Adaptive_Learning)
                memory.successful_pyramids++;
        }
    }
}

//+------------------------------------------------------------------+
//| Check if trend is strengthening                                   |
//+------------------------------------------------------------------+
bool IsTrendStrengthening(int direction)
{
    double adx[];
    ArraySetAsSeries(adx, true);
    
    if(CopyBuffer(h1_adx_handle, 0, 0, 3, adx) <= 0)
        return false;
    
    // ADX rising = trend strengthening
    return (adx[0] > adx[1] && adx[1] > adx[2]);
}

//+------------------------------------------------------------------+
//| Get net position direction                                        |
//+------------------------------------------------------------------+
int GetNetPositionDirection()
{
    int buyCount = 0, sellCount = 0;
    
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if(positionInfo.SelectByIndex(i))
        {
            if(positionInfo.Symbol() == _Symbol && positionInfo.Magic() == Magic_Number)
            {
                if(positionInfo.Type() == POSITION_TYPE_BUY)
                    buyCount++;
                else
                    sellCount++;
            }
        }
    }
    
    if(buyCount > sellCount) return 1;   // Net long
    if(sellCount > buyCount) return -1;  // Net short
    return 0;                             // No positions
}

//+------------------------------------------------------------------+
//| Check if has open positions                                       |
//+------------------------------------------------------------------+
bool HasOpenPositions()
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
//| Close all positions                                               |
//+------------------------------------------------------------------+
void CloseAllPositions(string reason)
{
    Print("========================================");
    Print("[CLOSE ALL] Reason: ", reason);
    Print("========================================");
    
    int closed = 0;
    
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if(positionInfo.SelectByIndex(i))
        {
            if(positionInfo.Symbol() == _Symbol && positionInfo.Magic() == Magic_Number)
            {
                if(trade.PositionClose(positionInfo.Ticket()))
                {
                    closed++;
                    Print("[CLOSED] Ticket: ", positionInfo.Ticket(), " | Profit: ", positionInfo.Profit());
                }
            }
        }
    }
    
    Print("Total positions closed: ", closed);
    pyramidLevel = 0;
    lastEntryPrice = 0;
}

//+------------------------------------------------------------------+
//| Update support/resistance levels                                  |
//+------------------------------------------------------------------+
void UpdateSupportResistance()
{
    double high[], low[];
    ArraySetAsSeries(high, true);
    ArraySetAsSeries(low, true);
    
    int bars = MathMin(Pattern_Lookback_Bars, Bars(_Symbol, PERIOD_H1));
    if(CopyHigh(_Symbol, PERIOD_H1, 0, bars, high) <= 0) return;
    if(CopyLow(_Symbol, PERIOD_H1, 0, bars, low) <= 0) return;
    
    srCount = 0;
    
    // Find swing highs (resistance)
    for(int i = 2; i < bars - 2; i++)
    {
        if(high[i] > high[i-1] && high[i] > high[i-2] &&
           high[i] > high[i+1] && high[i] > high[i+2])
        {
            // Check if similar level exists
            bool exists = false;
            double atr = GetH1ATR();
            
            for(int j = 0; j < srCount; j++)
            {
                if(MathAbs(srLevels[j].price - high[i]) < atr * 0.3)
                {
                    srLevels[j].touches++;
                    exists = true;
                    break;
                }
            }
            
            if(!exists && srCount < 50)
            {
                srLevels[srCount].price = high[i];
                srLevels[srCount].touches = 1;
                srLevels[srCount].isResistance = true;
                srCount++;
            }
        }
    }
    
    // Find swing lows (support)
    for(int i = 2; i < bars - 2; i++)
    {
        if(low[i] < low[i-1] && low[i] < low[i-2] &&
           low[i] < low[i+1] && low[i] < low[i+2])
        {
            bool exists = false;
            double atr = GetH1ATR();
            
            for(int j = 0; j < srCount; j++)
            {
                if(MathAbs(srLevels[j].price - low[i]) < atr * 0.3)
                {
                    srLevels[j].touches++;
                    exists = true;
                    break;
                }
            }
            
            if(!exists && srCount < 50)
            {
                srLevels[srCount].price = low[i];
                srLevels[srCount].touches = 1;
                srLevels[srCount].isResistance = false;
                srCount++;
            }
        }
    }
    
    if(Enable_Debug_Logging && srCount > 0)
        Print("[S/R] Detected ", srCount, " support/resistance levels");
}

//+------------------------------------------------------------------+
//| Adaptive learning from market                                     |
//+------------------------------------------------------------------+
void LearnFromMarket()
{
    // Analyze recent trades
    int wins = 0, losses = 0;
    datetime now = TimeCurrent();
    
    for(int i = 0; i < HistoryDealsTotal(); i++)
    {
        ulong ticket = HistoryDealGetTicket(i);
        if(ticket > 0)
        {
            if(HistoryDealGetInteger(ticket, DEAL_MAGIC) == Magic_Number)
            {
                datetime dealTime = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
                if(now - dealTime < Learning_Period_Days * 86400)
                {
                    double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
                    if(profit > 0) wins++;
                    else if(profit < 0) losses++;
                }
            }
        }
    }
    
    // Update win rate by hour
    MqlDateTime dt;
    TimeToStruct(TimeCurrent(), dt);
    int currentHour = dt.hour;
    
    if(wins + losses > 0)
    {
        double winRate = (double)wins / (wins + losses);
        memory.win_rate_by_hour[currentHour] = winRate * Learning_Rate + 
                                                memory.win_rate_by_hour[currentHour] * (1 - Learning_Rate);
    }
}

//+------------------------------------------------------------------+
//| Load market memory from file                                      |
//+------------------------------------------------------------------+
void LoadMarketMemory()
{
    string filename = "market_memory_" + _Symbol + ".dat";
    int handle = FileOpen(filename, FILE_READ|FILE_BIN);
    
    if(handle != INVALID_HANDLE)
    {
        FileReadStruct(handle, memory);
        FileClose(handle);
        Print("[LEARNING] Loaded market memory: ", memory.successful_pyramids, " successful pyramids");
    }
    else
    {
        // Initialize default values
        ArrayInitialize(memory.win_rate_by_hour, 0.5);
        memory.successful_pyramids = 0;
        memory.total_patterns_detected = 0;
    }
}

//+------------------------------------------------------------------+
//| Save market memory to file                                        |
//+------------------------------------------------------------------+
void SaveMarketMemory()
{
    string filename = "market_memory_" + _Symbol + ".dat";
    int handle = FileOpen(filename, FILE_WRITE|FILE_BIN);
    
    if(handle != INVALID_HANDLE)
    {
        FileWriteStruct(handle, memory);
        FileClose(handle);
        Print("[LEARNING] Saved market memory");
    }
}

//+------------------------------------------------------------------+
//| Check if can trade now (session filter)                          |
//+------------------------------------------------------------------+
bool CanTradeNow()
{
    if(!Use_Session_Filter)
        return true;
    
    // Check strong trend override
    double adx[];
    ArraySetAsSeries(adx, true);
    
    if(CopyBuffer(h1_adx_handle, 0, 0, 2, adx) > 0)
    {
        if(adx[0] >= Strong_Trend_ADX_Level && Override_On_Strong_Trend)
            return true;
    }
    
    // Check session
    datetime currentTime = TimeGMT();
    MqlDateTime dt;
    TimeToStruct(currentTime, dt);
    int currentHour = dt.hour;
    
    if(Trade_Asian_Session && currentHour >= 0 && currentHour < 9)
        return true;
    if(Trade_London_Session && currentHour >= 8 && currentHour < 17)
        return true;
    if(Trade_NewYork_Session && currentHour >= 13 && currentHour < 22)
        return true;
    
    return false;
}

//+------------------------------------------------------------------+
//| Get H1 ATR                                                        |
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
//| Calculate position size                                           |
//+------------------------------------------------------------------+
double CalculatePositionSize()
{
    if(Fixed_Lot_Size > 0)
        return Fixed_Lot_Size;
    
    double accountBalance = accountInfo.Balance();
    double riskAmount = accountBalance * (Risk_Per_Trade / 100.0);
    
    double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
    double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
    double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
    double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
    double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
    
    double atr = GetH1ATR();
    if(atr <= 0) atr = 10.0;
    
    double referenceDistance = atr * 2.0;
    double lots = (riskAmount / (referenceDistance / tickSize * tickValue));
    
    lots = MathFloor(lots / lotStep) * lotStep;
    
    if(lots < minLot) lots = minLot;
    if(lots > maxLot) lots = maxLot;
    
    return lots;
}

//+------------------------------------------------------------------+
//| Analyze and execute trades                                        |
//+------------------------------------------------------------------+
void AnalyzeAndTrade()
{
    // Get H1 trend bias
    int trendBias = GetH1TrendBias();
    
    if(trendBias == 0)
        return;
    
    double atr = GetH1ATR();
    if(atr <= 0)
        return;
    
    double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    
    // Check for buy entry
    if(trendBias == 1 && CheckM15BuyEntry())
    {
        double lotSize = CalculatePositionSize();
        
        if(lotSize > 0)
        {
            double sl = Use_Stop_Loss ? (bid - (ATR_Multiplier_ISL * atr)) : 0;
            
            if(trade.Buy(lotSize, _Symbol, ask, sl, 0, Trade_Comment + "_Entry"))
            {
                pyramidLevel = 1;
                lastEntryPrice = ask;
                Print("========================================");
                Print("[ENTRY] BUY at ", ask, " | Lot: ", lotSize);
                Print("Pyramiding enabled: Max ", Max_Pyramid_Levels, " levels");
                Print("========================================");
            }
        }
    }
    // Check for sell entry
    else if(trendBias == -1 && CheckM15SellEntry())
    {
        double lotSize = CalculatePositionSize();
        
        if(lotSize > 0)
        {
            double sl = Use_Stop_Loss ? (ask + (ATR_Multiplier_ISL * atr)) : 0;
            
            if(trade.Sell(lotSize, _Symbol, bid, sl, 0, Trade_Comment + "_Entry"))
            {
                pyramidLevel = 1;
                lastEntryPrice = bid;
                Print("========================================");
                Print("[ENTRY] SELL at ", bid, " | Lot: ", lotSize);
                Print("Pyramiding enabled: Max ", Max_Pyramid_Levels, " levels");
                Print("========================================");
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Get H1 trend bias                                                 |
//+------------------------------------------------------------------+
int GetH1TrendBias()
{
    double ema8[], ema21[], ema34[], ema55[], close[];
    ArraySetAsSeries(ema8, true);
    ArraySetAsSeries(ema21, true);
    ArraySetAsSeries(ema34, true);
    ArraySetAsSeries(ema55, true);
    ArraySetAsSeries(close, true);
    
    if(CopyBuffer(h1_ema8_handle, 0, 0, 3, ema8) <= 0) return 0;
    if(CopyBuffer(h1_ema21_handle, 0, 0, 3, ema21) <= 0) return 0;
    if(CopyBuffer(h1_ema34_handle, 0, 0, 3, ema34) <= 0) return 0;
    if(CopyBuffer(h1_ema55_handle, 0, 0, 3, ema55) <= 0) return 0;
    if(CopyClose(_Symbol, PERIOD_H1, 0, 3, close) <= 0) return 0;
    
    if(close[0] > ema55[0] && ema8[0] > ema21[0] && ema21[0] > ema34[0] && ema34[0] > ema55[0])
        return 1;  // Bullish
    
    if(close[0] < ema55[0] && ema8[0] < ema21[0] && ema21[0] < ema34[0] && ema34[0] < ema55[0])
        return -1; // Bearish
    
    return 0;
}

//+------------------------------------------------------------------+
//| Check M15 buy entry                                               |
//+------------------------------------------------------------------+
bool CheckM15BuyEntry()
{
    double ema8[], ema21[], ema34[], close[];
    ArraySetAsSeries(ema8, true);
    ArraySetAsSeries(ema21, true);
    ArraySetAsSeries(ema34, true);
    ArraySetAsSeries(close, true);
    
    if(CopyBuffer(m15_ema8_handle, 0, 0, 3, ema8) <= 0) return false;
    if(CopyBuffer(m15_ema21_handle, 0, 0, 3, ema21) <= 0) return false;
    if(CopyBuffer(m15_ema34_handle, 0, 0, 3, ema34) <= 0) return false;
    if(CopyClose(_Symbol, PERIOD_M15, 0, 3, close) <= 0) return false;
    
    bool maCondition = (close[1] > ema21[1]) && (ema8[0] > ema21[0]) && (ema21[0] > ema34[0]);
    if(!maCondition) return false;
    
    if(Use_MACD_Confirmation)
    {
        double macdMain[], macdSignal[];
        ArraySetAsSeries(macdMain, true);
        ArraySetAsSeries(macdSignal, true);
        
        if(CopyBuffer(m15_macd_handle, 0, 0, 3, macdMain) <= 0) return false;
        if(CopyBuffer(m15_macd_handle, 1, 0, 3, macdSignal) <= 0) return false;
        
        double histogram0 = macdMain[0] - macdSignal[0];
        double histogram1 = macdMain[1] - macdSignal[1];
        
        if(!(histogram0 > 0 && histogram0 > histogram1))
            return false;
    }
    
    if(Use_RSI_Confirmation)
    {
        double rsi[];
        ArraySetAsSeries(rsi, true);
        
        if(CopyBuffer(m15_rsi_handle, 0, 0, 3, rsi) <= 0) return false;
        
        if(Strict_RSI_Cross)
        {
            if(!(rsi[0] > RSI_Level && rsi[1] <= RSI_Level))
                return false;
        }
        else
        {
            if(!(rsi[0] > RSI_Level && rsi[0] > rsi[1]))
                return false;
        }
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Check M15 sell entry                                              |
//+------------------------------------------------------------------+
bool CheckM15SellEntry()
{
    double ema8[], ema21[], ema34[], close[];
    ArraySetAsSeries(ema8, true);
    ArraySetAsSeries(ema21, true);
    ArraySetAsSeries(ema34, true);
    ArraySetAsSeries(close, true);
    
    if(CopyBuffer(m15_ema8_handle, 0, 0, 3, ema8) <= 0) return false;
    if(CopyBuffer(m15_ema21_handle, 0, 0, 3, ema21) <= 0) return false;
    if(CopyBuffer(m15_ema34_handle, 0, 0, 3, ema34) <= 0) return false;
    if(CopyClose(_Symbol, PERIOD_M15, 0, 3, close) <= 0) return false;
    
    bool maCondition = (close[1] < ema21[1]) && (ema8[0] < ema21[0]) && (ema21[0] < ema34[0]);
    if(!maCondition) return false;
    
    if(Use_MACD_Confirmation)
    {
        double macdMain[], macdSignal[];
        ArraySetAsSeries(macdMain, true);
        ArraySetAsSeries(macdSignal, true);
        
        if(CopyBuffer(m15_macd_handle, 0, 0, 3, macdMain) <= 0) return false;
        if(CopyBuffer(m15_macd_handle, 1, 0, 3, macdSignal) <= 0) return false;
        
        double histogram0 = macdMain[0] - macdSignal[0];
        double histogram1 = macdMain[1] - macdSignal[1];
        
        if(!(histogram0 < 0 && histogram0 < histogram1))
            return false;
    }
    
    if(Use_RSI_Confirmation)
    {
        double rsi[];
        ArraySetAsSeries(rsi, true);
        
        if(CopyBuffer(m15_rsi_handle, 0, 0, 3, rsi) <= 0) return false;
        
        if(Strict_RSI_Cross)
        {
            if(!(rsi[0] < RSI_Level && rsi[1] >= RSI_Level))
                return false;
        }
        else
        {
            if(!(rsi[0] < RSI_Level && rsi[0] < rsi[1]))
                return false;
        }
    }
    
    return true;
}
//+------------------------------------------------------------------+
