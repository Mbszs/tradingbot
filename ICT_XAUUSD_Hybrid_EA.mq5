//+------------------------------------------------------------------+
//|                                        ICT_XAUUSD_Hybrid_EA.mq5 |
//|                                    ICT Smart Money Concepts EA |
//|                                         For XAUUSD Trading Only |
//+------------------------------------------------------------------+
#property copyright "ICT XAUUSD Hybrid EA"
#property link      ""
#property version   "1.01"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

//--- Input Parameters
input group "=== Risk Management ==="
input double InpRiskPercent = 1.0;              // Risk % per trade
input double InpMaxDailyDrawdown = 3.0;         // Max daily drawdown %
input int InpMaxTradesPerSession = 2;           // Max trades per session
input double InpTPRiskReward = 1.5;             // Take Profit Risk:Reward
input bool InpUsePartialTP = false;             // Use Partial TP at 1:1
input bool InpUseBreakEven = true;              // Move to break-even at 1R

input group "=== Session Settings ==="
input int InpAsiaStartHour = 23;                // Asia Start Hour (GMT)
input int InpAsiaEndHour = 6;                   // Asia End Hour (GMT)
input int InpLondonStartHour = 7;               // London Start Hour (GMT)
input int InpLondonEndHour = 11;                // London End Hour (GMT)

input group "=== ICT Settings ==="
input int InpSwingLookback = 20;                // Swing High/Low lookback
input int InpOBMinBodyPoints = 50;              // Min OB body size (points)
input double InpFibOTELow = 0.62;               // OTE Fib Low
input double InpFibOTEHigh = 0.79;              // OTE Fib High
input int InpSLBufferPoints = 10;               // Stop Loss buffer (points)

input group "=== Quantitative Filters ==="
input int InpATRPeriod = 14;                    // ATR Period
input double InpATRMinMultiplier = 0.6;         // ATR Min Multiplier
input double InpATRMaxMultiplier = 2.0;         // ATR Max Multiplier
input int InpVolumeLookback = 20;               // Volume lookback bars
input double InpVolumeMultiplier = 1.0;         // Volume threshold multiplier
input double InpConfidenceThreshold = 0.7;      // Min confidence score
input int InpMaxSpreadPoints = 2000;            // Max spread (points)

input group "=== Visualization ==="
input bool InpShowLevels = true;                // Show session levels
input bool InpShowZones = true;                 // Show OB/FVG zones
input bool InpShowLabels = true;                // Show trade labels

input group "=== Safety ==="
input bool InpEnableCircuitBreaker = true;      // Enable circuit breaker
input bool InpNoTradeFriday = true;             // No trades Friday > 20:00
input int InpMagicNumber = 123456;              // Magic Number

//--- Global Objects
CTrade trade;
CPositionInfo position;
CAccountInfo account;

//--- Session Structure
struct SessionData {
    datetime startTime;
    datetime endTime;
    double high;
    double low;
    double mid;
    bool isActive;
    string name;
};

//--- Trade Zone Structure
struct TradeZone {
    double priceHigh;
    double priceLow;
    datetime time;
    string type;  // "OB", "FVG", "OTE"
    bool isBullish;
    bool isValid;
};

//--- Market Structure
struct MarketStructure {
    double lastSwingHigh;
    double lastSwingLow;
    datetime lastHighTime;
    datetime lastLowTime;
    int trend;  // 1=bullish, -1=bearish, 0=neutral
    bool mssDetected;
    bool chochDetected;
};

//--- Liquidity Sweep
struct LiquiditySweep {
    bool sweepAbove;
    bool sweepBelow;
    datetime sweepTime;
    double sweepPrice;
    int sweepDirection;  // 1=buy setup, -1=sell setup
};

//--- Global Variables
SessionData g_previousSession;
SessionData g_currentSession;
MarketStructure g_structure;
LiquiditySweep g_sweep;
TradeZone g_zones[];
int g_tradesThisSession = 0;
double g_startingBalance = 0;
double g_dailyPL = 0;
bool g_tradingEnabled = true;
datetime g_lastBarTime = 0;
datetime g_currentDay = 0;

//--- Handles
int g_atrHandle = INVALID_HANDLE;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    // Set magic number
    trade.SetExpertMagicNumber(InpMagicNumber);
    trade.SetDeviationInPoints(50);
    trade.SetTypeFilling(GetFillingMode());
    trade.SetAsyncMode(false);
    
    // Initialize ATR
    g_atrHandle = iATR(_Symbol, PERIOD_M5, InpATRPeriod);
    if(g_atrHandle == INVALID_HANDLE) {
        Print("Failed to create ATR indicator");
        return INIT_FAILED;
    }
    
    // Validate symbol
    if(_Symbol != "XAUUSD" && _Symbol != "XAUUSD.pro" && _Symbol != "XAUUSDm" && 
       StringFind(_Symbol, "XAU") == -1) {
        Print("Warning: This EA is designed for XAUUSD only. Current symbol: ", _Symbol);
    }
    
    // Initialize starting balance
    g_startingBalance = account.Equity();
    g_currentDay = TimeCurrent() - (TimeCurrent() % 86400);
    
    // Initialize structures
    InitializeStructures();
    
    Print("ICT XAUUSD Hybrid EA initialized successfully");
    Print("Risk per trade: ", InpRiskPercent, "%");
    Print("Max daily drawdown: ", InpMaxDailyDrawdown, "%");
    Print("Confidence threshold: ", InpConfidenceThreshold);
    
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    // Release indicator handle
    if(g_atrHandle != INVALID_HANDLE)
        IndicatorRelease(g_atrHandle);
    
    // Clean up objects
    ObjectsDeleteAll(0, "ICT_");
    
    Print("ICT XAUUSD Hybrid EA deinitialized");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
    // Check for new bar
    datetime currentBarTime = iTime(_Symbol, PERIOD_M5, 0);
    if(currentBarTime == g_lastBarTime)
        return;
    g_lastBarTime = currentBarTime;
    
    // Daily reset check
    CheckDailyReset();
    
    // Update session data
    UpdateSessionData();
    
    // Update market structure
    UpdateMarketStructure();

    // Detect liquidity sweeps
    DetectLiquiditySweeps();

    // Update trade zones
    UpdateTradeZones();

    // Manage open positions (must run even outside sessions so
    // break-even and partial TP keep working after session close)
    ManageOpenPositions();

    // Update visualization
    if(InpShowLevels)
        DrawSessionLevels();
    if(InpShowZones)
        DrawTradeZones();

    // Check if trading is allowed
    if(!IsTradingAllowed())
        return;

    // Check for entry signals
    if(g_tradesThisSession < InpMaxTradesPerSession)
        CheckForEntrySignal();
}

//+------------------------------------------------------------------+
//| Pick a filling mode supported by the broker                      |
//+------------------------------------------------------------------+
ENUM_ORDER_TYPE_FILLING GetFillingMode()
{
    long filling = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
    if((filling & SYMBOL_FILLING_FOK) != 0) return ORDER_FILLING_FOK;
    if((filling & SYMBOL_FILLING_IOC) != 0) return ORDER_FILLING_IOC;
    return ORDER_FILLING_RETURN;
}

//+------------------------------------------------------------------+
//| Select this EA's position on the chart symbol (by magic number)  |
//+------------------------------------------------------------------+
bool SelectOwnPosition()
{
    for(int i = PositionsTotal() - 1; i >= 0; i--) {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
           PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
            return true;
    }
    return false;
}

//+------------------------------------------------------------------+
//| Initialize structures                                            |
//+------------------------------------------------------------------+
void InitializeStructures()
{
    g_previousSession.high = 0;
    g_previousSession.low = DBL_MAX;
    g_previousSession.isActive = false;
    
    g_currentSession.high = 0;
    g_currentSession.low = DBL_MAX;
    g_currentSession.isActive = false;
    
    g_structure.trend = 0;
    g_structure.mssDetected = false;
    g_structure.chochDetected = false;
    
    g_sweep.sweepAbove = false;
    g_sweep.sweepBelow = false;
    g_sweep.sweepDirection = 0;
    
    ArrayResize(g_zones, 0);
}

//+------------------------------------------------------------------+
//| Check daily reset                                                |
//+------------------------------------------------------------------+
void CheckDailyReset()
{
    datetime todayStart = TimeCurrent() - (TimeCurrent() % 86400);

    if(todayStart != g_currentDay) {
        // New day - reset counters
        g_currentDay = todayStart;
        g_startingBalance = account.Equity();
        g_dailyPL = 0;
        g_tradesThisSession = 0;
        g_tradingEnabled = true;
        
        Print("New trading day started. Balance: ", g_startingBalance);
    }
    
    if(g_startingBalance <= 0)
        return;

    // Calculate daily P/L from equity so floating losses count too
    g_dailyPL = account.Equity() - g_startingBalance;
    double dailyDrawdownPercent = (g_dailyPL / g_startingBalance) * 100;
    
    // Circuit breaker check
    if(InpEnableCircuitBreaker && dailyDrawdownPercent <= -InpMaxDailyDrawdown) {
        if(g_tradingEnabled) {
            g_tradingEnabled = false;
            Print("CIRCUIT BREAKER ACTIVATED! Daily drawdown: ", dailyDrawdownPercent, "%");
            CloseAllPositions();
        }
    }
}

//+------------------------------------------------------------------+
//| Update session data                                              |
//+------------------------------------------------------------------+
void UpdateSessionData()
{
    MqlDateTime timeStruct;
    TimeToStruct(TimeCurrent(), timeStruct);
    int currentHour = timeStruct.hour;
    
    bool wasActive = g_currentSession.isActive;
    
    // Check Asia session
    bool isAsiaSession = false;
    if(InpAsiaStartHour > InpAsiaEndHour) {
        // Crosses midnight
        isAsiaSession = (currentHour >= InpAsiaStartHour || currentHour < InpAsiaEndHour);
    } else {
        isAsiaSession = (currentHour >= InpAsiaStartHour && currentHour < InpAsiaEndHour);
    }
    
    // Check London session
    bool isLondonSession = (currentHour >= InpLondonStartHour && currentHour < InpLondonEndHour);
    
    // Session transition logic. A new session also begins when one
    // session hands over directly to the next (back-to-back hours)
    string desiredName = isAsiaSession ? "Asia" : "London";
    bool sessionChange = wasActive && (isAsiaSession || isLondonSession) &&
                         g_currentSession.name != desiredName;

    if(((isAsiaSession || isLondonSession) && !wasActive) || sessionChange) {
        // Session started - save previous
        if(g_currentSession.high > 0) {
            g_previousSession = g_currentSession;
        }

        // Reset current session
        g_currentSession.high = 0;
        g_currentSession.low = DBL_MAX;
        g_currentSession.isActive = true;
        g_currentSession.name = desiredName;
        g_tradesThisSession = 0;
        
        Print("Session started: ", g_currentSession.name);
    }
    else if(!isAsiaSession && !isLondonSession && wasActive) {
        // Session ended
        g_currentSession.isActive = false;
        Print("Session ended: ", g_currentSession.name);
    }
    
    // Update current session high/low
    if(g_currentSession.isActive) {
        double high = iHigh(_Symbol, PERIOD_M5, 1);
        double low = iLow(_Symbol, PERIOD_M5, 1);
        
        if(high > g_currentSession.high)
            g_currentSession.high = high;
        if(low < g_currentSession.low)
            g_currentSession.low = low;
            
        g_currentSession.mid = (g_currentSession.high + g_currentSession.low) / 2;
    }
}

//+------------------------------------------------------------------+
//| Check if trading is allowed                                      |
//+------------------------------------------------------------------+
bool IsTradingAllowed()
{
    if(!g_tradingEnabled)
        return false;
    
    if(!g_currentSession.isActive)
        return false;
    
    // No trades Friday after 20:00
    if(InpNoTradeFriday) {
        MqlDateTime timeStruct;
        TimeToStruct(TimeCurrent(), timeStruct);
        if(timeStruct.day_of_week == 5 && timeStruct.hour >= 20)
            return false;
    }
    
    // Check spread
    long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
    if(spread > InpMaxSpreadPoints) {
        Print("Spread too wide: ", spread);
        return false;
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Update market structure (MSS/CHOCH)                              |
//+------------------------------------------------------------------+
void UpdateMarketStructure()
{
    int lookback = InpSwingLookback;
    
    // Find swing high / low
    int highestBar = iHighest(_Symbol, PERIOD_M5, MODE_HIGH, lookback, 1);
    int lowestBar = iLowest(_Symbol, PERIOD_M5, MODE_LOW, lookback, 1);
    if(highestBar < 0 || lowestBar < 0)
        return; // history not loaded yet

    double swingHigh = iHigh(_Symbol, PERIOD_M5, highestBar);
    datetime swingHighTime = iTime(_Symbol, PERIOD_M5, highestBar);
    double swingLow = iLow(_Symbol, PERIOD_M5, lowestBar);
    datetime swingLowTime = iTime(_Symbol, PERIOD_M5, lowestBar);

    // Detect MSS (Market Structure Shift)
    g_structure.mssDetected = false;

    // Seed reference levels on the first run so a comparison against
    // zero-initialized values doesn't fire a spurious MSS
    if(g_structure.lastSwingHigh == 0 || g_structure.lastSwingLow == 0) {
        g_structure.lastSwingHigh = swingHigh;
        g_structure.lastSwingLow = swingLow;
        g_structure.lastHighTime = swingHighTime;
        g_structure.lastLowTime = swingLowTime;
        return;
    }
    
    if(swingHigh > g_structure.lastSwingHigh && swingLow > g_structure.lastSwingLow) {
        // Bullish MSS
        if(g_structure.trend != 1) {
            g_structure.mssDetected = true;
            g_structure.trend = 1;
            Print("Bullish MSS detected at ", swingHigh);
        }
    }
    else if(swingLow < g_structure.lastSwingLow && swingHigh < g_structure.lastSwingHigh) {
        // Bearish MSS
        if(g_structure.trend != -1) {
            g_structure.mssDetected = true;
            g_structure.trend = -1;
            Print("Bearish MSS detected at ", swingLow);
        }
    }
    
    // Update structure
    g_structure.lastSwingHigh = swingHigh;
    g_structure.lastSwingLow = swingLow;
    g_structure.lastHighTime = swingHighTime;
    g_structure.lastLowTime = swingLowTime;
}

//+------------------------------------------------------------------+
//| Detect liquidity sweeps                                          |
//+------------------------------------------------------------------+
void DetectLiquiditySweeps()
{
    if(g_previousSession.high == 0)
        return;
    
    double currentHigh = iHigh(_Symbol, PERIOD_M5, 1);
    double currentLow = iLow(_Symbol, PERIOD_M5, 1);
    double currentClose = iClose(_Symbol, PERIOD_M5, 1);
    
    double prevHigh = g_previousSession.high;
    double prevLow = g_previousSession.low;
    
    // Reset sweep flags
    g_sweep.sweepAbove = false;
    g_sweep.sweepBelow = false;
    
    // Detect sweep above (sell setup)
    if(currentHigh > prevHigh && currentClose < prevHigh) {
        g_sweep.sweepAbove = true;
        g_sweep.sweepDirection = -1;  // Bearish
        g_sweep.sweepPrice = prevHigh;
        g_sweep.sweepTime = iTime(_Symbol, PERIOD_M5, 1);
        Print("Liquidity sweep ABOVE detected at ", prevHigh, " - Bearish setup");
    }
    
    // Detect sweep below (buy setup)
    if(currentLow < prevLow && currentClose > prevLow) {
        g_sweep.sweepBelow = true;
        g_sweep.sweepDirection = 1;  // Bullish
        g_sweep.sweepPrice = prevLow;
        g_sweep.sweepTime = iTime(_Symbol, PERIOD_M5, 1);
        Print("Liquidity sweep BELOW detected at ", prevLow, " - Bullish setup");
    }
}

//+------------------------------------------------------------------+
//| Update trade zones (OB, FVG, OTE)                                |
//+------------------------------------------------------------------+
void UpdateTradeZones()
{
    ArrayResize(g_zones, 0);
    
    // Find Order Blocks
    FindOrderBlocks();
    
    // Find Fair Value Gaps
    FindFairValueGaps();
    
    // Calculate OTE zones from last impulse
    CalculateOTEZones();
}

//+------------------------------------------------------------------+
//| Find Order Blocks                                                |
//+------------------------------------------------------------------+
void FindOrderBlocks()
{
    for(int i = 2; i < 50; i++) {
        double body1 = MathAbs(iClose(_Symbol, PERIOD_M5, i) - iOpen(_Symbol, PERIOD_M5, i));
        double body2 = MathAbs(iClose(_Symbol, PERIOD_M5, i-1) - iOpen(_Symbol, PERIOD_M5, i-1));
        
        bool isBearishCandle = iClose(_Symbol, PERIOD_M5, i) < iOpen(_Symbol, PERIOD_M5, i);
        bool isBullishImpulse = (iClose(_Symbol, PERIOD_M5, i-1) - iOpen(_Symbol, PERIOD_M5, i-1)) > InpOBMinBodyPoints * _Point;
        
        bool isBullishCandle = iClose(_Symbol, PERIOD_M5, i) > iOpen(_Symbol, PERIOD_M5, i);
        bool isBearishImpulse = (iOpen(_Symbol, PERIOD_M5, i-1) - iClose(_Symbol, PERIOD_M5, i-1)) > InpOBMinBodyPoints * _Point;
        
        // Bullish OB
        if(isBearishCandle && isBullishImpulse && body1 > InpOBMinBodyPoints * _Point) {
            TradeZone zone;
            zone.priceHigh = iHigh(_Symbol, PERIOD_M5, i);
            zone.priceLow = iLow(_Symbol, PERIOD_M5, i);
            zone.time = iTime(_Symbol, PERIOD_M5, i);
            zone.type = "OB";
            zone.isBullish = true;
            zone.isValid = true;
            ArrayResize(g_zones, ArraySize(g_zones) + 1);
            g_zones[ArraySize(g_zones) - 1] = zone;
        }
        
        // Bearish OB
        if(isBullishCandle && isBearishImpulse && body1 > InpOBMinBodyPoints * _Point) {
            TradeZone zone;
            zone.priceHigh = iHigh(_Symbol, PERIOD_M5, i);
            zone.priceLow = iLow(_Symbol, PERIOD_M5, i);
            zone.time = iTime(_Symbol, PERIOD_M5, i);
            zone.type = "OB";
            zone.isBullish = false;
            zone.isValid = true;
            ArrayResize(g_zones, ArraySize(g_zones) + 1);
            g_zones[ArraySize(g_zones) - 1] = zone;
        }
    }
}

//+------------------------------------------------------------------+
//| Find Fair Value Gaps                                             |
//+------------------------------------------------------------------+
void FindFairValueGaps()
{
    for(int i = 3; i < 50; i++) {
        double high1 = iHigh(_Symbol, PERIOD_M5, i);
        double low1 = iLow(_Symbol, PERIOD_M5, i);
        double high3 = iHigh(_Symbol, PERIOD_M5, i-2);
        double low3 = iLow(_Symbol, PERIOD_M5, i-2);
        
        // Bullish FVG
        if(high1 < low3) {
            TradeZone zone;
            zone.priceHigh = low3;
            zone.priceLow = high1;
            zone.time = iTime(_Symbol, PERIOD_M5, i-1);
            zone.type = "FVG";
            zone.isBullish = true;
            zone.isValid = true;
            ArrayResize(g_zones, ArraySize(g_zones) + 1);
            g_zones[ArraySize(g_zones) - 1] = zone;
        }
        
        // Bearish FVG
        if(low1 > high3) {
            TradeZone zone;
            zone.priceHigh = low1;
            zone.priceLow = high3;
            zone.time = iTime(_Symbol, PERIOD_M5, i-1);
            zone.type = "FVG";
            zone.isBullish = false;
            zone.isValid = true;
            ArrayResize(g_zones, ArraySize(g_zones) + 1);
            g_zones[ArraySize(g_zones) - 1] = zone;
        }
    }
}

//+------------------------------------------------------------------+
//| Calculate OTE (Optimal Trade Entry) zones                        |
//+------------------------------------------------------------------+
void CalculateOTEZones()
{
    if(g_structure.trend == 0)
        return;
    
    double high = g_structure.lastSwingHigh;
    double low = g_structure.lastSwingLow;
    double range = high - low;
    
    if(g_structure.trend == 1) {
        // Bullish OTE
        TradeZone zone;
        zone.priceHigh = low + range * InpFibOTEHigh;
        zone.priceLow = low + range * InpFibOTELow;
        zone.time = TimeCurrent();
        zone.type = "OTE";
        zone.isBullish = true;
        zone.isValid = true;
        ArrayResize(g_zones, ArraySize(g_zones) + 1);
        g_zones[ArraySize(g_zones) - 1] = zone;
    }
    else if(g_structure.trend == -1) {
        // Bearish OTE
        TradeZone zone;
        zone.priceHigh = high - range * InpFibOTELow;
        zone.priceLow = high - range * InpFibOTEHigh;
        zone.time = TimeCurrent();
        zone.type = "OTE";
        zone.isBullish = false;
        zone.isValid = true;
        ArrayResize(g_zones, ArraySize(g_zones) + 1);
        g_zones[ArraySize(g_zones) - 1] = zone;
    }
}

//+------------------------------------------------------------------+
//| Calculate confidence score                                       |
//+------------------------------------------------------------------+
double CalculateConfidenceScore(bool isBuy)
{
    double score = 0.0;
    
    // Liquidity sweep (0.25)
    if((isBuy && g_sweep.sweepBelow) || (!isBuy && g_sweep.sweepAbove)) {
        score += 0.25;
    }
    
    // MSS/CHOCH alignment (0.20)
    if((isBuy && g_structure.trend == 1) || (!isBuy && g_structure.trend == -1)) {
        score += 0.20;
    }
    
    // OB/FVG confluence (0.25)
    int confluenceCount = 0;
    double currentPrice = iClose(_Symbol, PERIOD_M5, 0);
    for(int i = 0; i < ArraySize(g_zones); i++) {
        if(g_zones[i].isBullish == isBuy && 
           currentPrice >= g_zones[i].priceLow && 
           currentPrice <= g_zones[i].priceHigh) {
            confluenceCount++;
        }
    }
    if(confluenceCount >= 2)
        score += 0.25;
    else if(confluenceCount == 1)
        score += 0.15;
    
    // Volume filter (0.10)
    if(CheckVolumeFilter())
        score += 0.10;
    
    // ATR filter (0.10)
    if(CheckATRFilter())
        score += 0.10;
    
    // HTF bias (0.10) - simplified to match H1 structure
    double h1High = iHigh(_Symbol, PERIOD_H1, 1);
    double h1Low = iLow(_Symbol, PERIOD_H1, 1);
    double h1PrevHigh = iHigh(_Symbol, PERIOD_H1, 2);
    double h1PrevLow = iLow(_Symbol, PERIOD_H1, 2);
    
    if(isBuy && h1High > h1PrevHigh && h1Low > h1PrevLow)
        score += 0.10;
    else if(!isBuy && h1Low < h1PrevLow && h1High < h1PrevHigh)
        score += 0.10;
    
    return score;
}

//+------------------------------------------------------------------+
//| Check ATR filter                                                 |
//+------------------------------------------------------------------+
bool CheckATRFilter()
{
    double atr[];
    ArraySetAsSeries(atr, true);
    // Start at shift 1: the forming bar's ATR value is not final yet
    if(CopyBuffer(g_atrHandle, 0, 1, 20, atr) < 20)
        return false;

    double currentATR = atr[0];
    double avgATR = 0;
    for(int i = 0; i < 20; i++)
        avgATR += atr[i];
    avgATR /= 20;
    if(avgATR <= 0)
        return false;

    double ratio = currentATR / avgATR;
    
    if(ratio >= InpATRMinMultiplier && ratio <= InpATRMaxMultiplier)
        return true;
    
    return false;
}

//+------------------------------------------------------------------+
//| Check volume filter                                              |
//+------------------------------------------------------------------+
bool CheckVolumeFilter()
{
    long volumes[];
    ArraySetAsSeries(volumes, true);
    // Compare the last CLOSED bar against the average of the bars before
    // it. The EA runs on the first tick of a new bar, so the forming
    // bar's volume is near zero and would always fail the filter.
    if(CopyTickVolume(_Symbol, PERIOD_M5, 1, InpVolumeLookback + 1, volumes) < InpVolumeLookback + 1)
        return false;

    long lastClosedVolume = volumes[0];
    long avgVolume = 0;
    for(int i = 1; i <= InpVolumeLookback; i++)
        avgVolume += volumes[i];
    avgVolume /= InpVolumeLookback;

    if(lastClosedVolume >= avgVolume * InpVolumeMultiplier)
        return true;
    
    return false;
}

//+------------------------------------------------------------------+
//| Check for entry signal                                           |
//+------------------------------------------------------------------+
void CheckForEntrySignal()
{
    // Don't trade if this EA already has a position
    if(SelectOwnPosition())
        return;
    
    double currentPrice = iClose(_Symbol, PERIOD_M5, 0);
    
    // Check for buy setup
    if(g_sweep.sweepBelow && g_structure.trend == 1) {
        // Check if price is in a valid zone
        for(int i = 0; i < ArraySize(g_zones); i++) {
            if(g_zones[i].isBullish && g_zones[i].isValid &&
               currentPrice >= g_zones[i].priceLow && 
               currentPrice <= g_zones[i].priceHigh) {
                
                double confidence = CalculateConfidenceScore(true);
                if(confidence >= InpConfidenceThreshold) {
                    ExecuteBuyTrade(g_zones[i]);
                    return;
                }
            }
        }
    }
    
    // Check for sell setup
    if(g_sweep.sweepAbove && g_structure.trend == -1) {
        // Check if price is in a valid zone
        for(int i = 0; i < ArraySize(g_zones); i++) {
            if(!g_zones[i].isBullish && g_zones[i].isValid &&
               currentPrice >= g_zones[i].priceLow && 
               currentPrice <= g_zones[i].priceHigh) {
                
                double confidence = CalculateConfidenceScore(false);
                if(confidence >= InpConfidenceThreshold) {
                    ExecuteSellTrade(g_zones[i]);
                    return;
                }
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Execute buy trade                                                |
//+------------------------------------------------------------------+
void ExecuteBuyTrade(TradeZone &zone)
{
    double entryPrice = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    double sl = zone.priceLow - InpSLBufferPoints * _Point;
    double slDistance = entryPrice - sl;
    double minStopDistance = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;

    if(slDistance <= minStopDistance) {
        Print("BUY skipped: invalid SL distance ", DoubleToString(slDistance, _Digits));
        return;
    }

    double tp = entryPrice + slDistance * InpTPRiskReward;

    // Calculate lot size
    double lotSize = CalculateLotSize(slDistance);
    if(lotSize <= 0) {
        Print("BUY skipped: risk too small for broker minimum lot");
        return;
    }

    // Execute trade
    if(trade.Buy(lotSize, _Symbol, entryPrice, sl, tp, "ICT Buy - " + zone.type)) {
        g_tradesThisSession++;
        Print("BUY executed: Entry=", entryPrice, " SL=", sl, " TP=", tp, " Lots=", lotSize, " Zone=", zone.type);
        
        // Draw entry arrow
        if(InpShowLabels) {
            string objName = "ICT_Entry_" + IntegerToString(TimeCurrent());
            ObjectCreate(0, objName, OBJ_ARROW_BUY, 0, TimeCurrent(), entryPrice);
            ObjectSetInteger(0, objName, OBJPROP_COLOR, clrLime);
            ObjectSetInteger(0, objName, OBJPROP_WIDTH, 3);
        }
    } else {
        Print("BUY order failed: ", trade.ResultRetcodeDescription());
    }
}

//+------------------------------------------------------------------+
//| Execute sell trade                                               |
//+------------------------------------------------------------------+
void ExecuteSellTrade(TradeZone &zone)
{
    double entryPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    double sl = zone.priceHigh + InpSLBufferPoints * _Point;
    double slDistance = sl - entryPrice;
    double minStopDistance = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;

    if(slDistance <= minStopDistance) {
        Print("SELL skipped: invalid SL distance ", DoubleToString(slDistance, _Digits));
        return;
    }

    double tp = entryPrice - slDistance * InpTPRiskReward;

    // Calculate lot size
    double lotSize = CalculateLotSize(slDistance);
    if(lotSize <= 0) {
        Print("SELL skipped: risk too small for broker minimum lot");
        return;
    }

    // Execute trade
    if(trade.Sell(lotSize, _Symbol, entryPrice, sl, tp, "ICT Sell - " + zone.type)) {
        g_tradesThisSession++;
        Print("SELL executed: Entry=", entryPrice, " SL=", sl, " TP=", tp, " Lots=", lotSize, " Zone=", zone.type);
        
        // Draw entry arrow
        if(InpShowLabels) {
            string objName = "ICT_Entry_" + IntegerToString(TimeCurrent());
            ObjectCreate(0, objName, OBJ_ARROW_SELL, 0, TimeCurrent(), entryPrice);
            ObjectSetInteger(0, objName, OBJPROP_COLOR, clrRed);
            ObjectSetInteger(0, objName, OBJPROP_WIDTH, 3);
        }
    } else {
        Print("SELL order failed: ", trade.ResultRetcodeDescription());
    }
}

//+------------------------------------------------------------------+
//| Calculate lot size based on risk                                 |
//+------------------------------------------------------------------+
double CalculateLotSize(double slDistance)
{
    double accountBalance = account.Balance();
    double riskAmount = accountBalance * (InpRiskPercent / 100.0);
    
    double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
    double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
    double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
    double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
    double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
    
    if(slDistance <= 0 || tickSize <= 0 || tickValue <= 0 || lotStep <= 0)
        return 0;

    double lotSize = riskAmount / (slDistance / tickSize * tickValue);

    // Normalize lot size
    lotSize = MathFloor(lotSize / lotStep) * lotStep;

    // Never round UP to the minimum lot: that would risk more than the
    // configured percentage. Skip the trade instead.
    if(lotSize < minLot)
        return 0;

    return MathMin(maxLot, lotSize);
}

//+------------------------------------------------------------------+
//| Manage open positions                                            |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
    static ulong s_partialDoneTicket = 0;

    if(!SelectOwnPosition())
        return;

    ulong ticket = (ulong)PositionGetInteger(POSITION_TICKET);
    double positionOpenPrice = PositionGetDouble(POSITION_PRICE_OPEN);
    double positionSL = PositionGetDouble(POSITION_SL);
    double positionTP = PositionGetDouble(POSITION_TP);
    long positionType = PositionGetInteger(POSITION_TYPE);
    double currentPrice = (positionType == POSITION_TYPE_BUY) ?
                          SymbolInfoDouble(_Symbol, SYMBOL_BID) :
                          SymbolInfoDouble(_Symbol, SYMBOL_ASK);

    double slDistance = MathAbs(positionOpenPrice - positionSL);
    double profit = (positionType == POSITION_TYPE_BUY) ?
                    (currentPrice - positionOpenPrice) :
                    (positionOpenPrice - currentPrice);

    if(slDistance <= 0 || profit < slDistance)
        return;

    // Partial TP at 1:1 - once per position, via a true partial close
    // (an opposite market order would OPEN a new position on hedging
    // accounts instead of reducing this one)
    if(InpUsePartialTP && ticket != s_partialDoneTicket) {
        double currentVolume = PositionGetDouble(POSITION_VOLUME);
        double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
        double partialVolume = MathFloor(currentVolume * 0.5 / lotStep) * lotStep;

        if(partialVolume >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN) &&
           partialVolume < currentVolume) {
            if(trade.PositionClosePartial(ticket, partialVolume)) {
                s_partialDoneTicket = ticket;
                Print("Partial TP executed: 50% closed at 1:1");
            }
        } else {
            s_partialDoneTicket = ticket; // volume too small to split
        }
    }

    // Move to break-even at 1R
    if(InpUseBreakEven && MathAbs(positionSL - positionOpenPrice) > 10 * _Point) {
        if(trade.PositionModify(ticket, positionOpenPrice, positionTP))
            Print("Position moved to break-even");
    }
}

//+------------------------------------------------------------------+
//| Close all positions                                              |
//+------------------------------------------------------------------+
void CloseAllPositions()
{
    for(int i = PositionsTotal() - 1; i >= 0; i--) {
        ulong ticket = PositionGetTicket(i);
        if(PositionSelectByTicket(ticket)) {
            // Only touch this EA's own positions, never manual trades
            // or positions of other EAs on the same account
            if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
               PositionGetInteger(POSITION_MAGIC) == InpMagicNumber) {
                trade.PositionClose(ticket);
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Draw session levels                                              |
//+------------------------------------------------------------------+
void DrawSessionLevels()
{
    if(g_previousSession.high == 0)
        return;
    
    // Previous session high
    string objNameHigh = "ICT_Prev_High";
    if(ObjectFind(0, objNameHigh) == -1) {
        ObjectCreate(0, objNameHigh, OBJ_HLINE, 0, 0, g_previousSession.high);
        ObjectSetInteger(0, objNameHigh, OBJPROP_COLOR, clrRed);
        ObjectSetInteger(0, objNameHigh, OBJPROP_STYLE, STYLE_DASH);
        ObjectSetInteger(0, objNameHigh, OBJPROP_WIDTH, 1);
    } else {
        ObjectSetDouble(0, objNameHigh, OBJPROP_PRICE, g_previousSession.high);
    }
    
    // Previous session low
    string objNameLow = "ICT_Prev_Low";
    if(ObjectFind(0, objNameLow) == -1) {
        ObjectCreate(0, objNameLow, OBJ_HLINE, 0, 0, g_previousSession.low);
        ObjectSetInteger(0, objNameLow, OBJPROP_COLOR, clrLime);
        ObjectSetInteger(0, objNameLow, OBJPROP_STYLE, STYLE_DASH);
        ObjectSetInteger(0, objNameLow, OBJPROP_WIDTH, 1);
    } else {
        ObjectSetDouble(0, objNameLow, OBJPROP_PRICE, g_previousSession.low);
    }
    
    // Previous session mid
    string objNameMid = "ICT_Prev_Mid";
    double prevMid = (g_previousSession.high + g_previousSession.low) / 2;
    if(ObjectFind(0, objNameMid) == -1) {
        ObjectCreate(0, objNameMid, OBJ_HLINE, 0, 0, prevMid);
        ObjectSetInteger(0, objNameMid, OBJPROP_COLOR, clrYellow);
        ObjectSetInteger(0, objNameMid, OBJPROP_STYLE, STYLE_DOT);
        ObjectSetInteger(0, objNameMid, OBJPROP_WIDTH, 1);
    } else {
        ObjectSetDouble(0, objNameMid, OBJPROP_PRICE, prevMid);
    }
}

//+------------------------------------------------------------------+
//| Draw trade zones                                                 |
//+------------------------------------------------------------------+
void DrawTradeZones()
{
    // Clean old zones
    for(int i = ObjectsTotal(0, 0, OBJ_RECTANGLE) - 1; i >= 0; i--) {
        string objName = ObjectName(0, i, 0, OBJ_RECTANGLE);
        if(StringFind(objName, "ICT_Zone_") != -1) {
            ObjectDelete(0, objName);
        }
    }
    
    // Draw current zones
    for(int i = 0; i < ArraySize(g_zones) && i < 10; i++) {
        if(!g_zones[i].isValid)
            continue;
        
        string objName = "ICT_Zone_" + IntegerToString(i);
        datetime timeEnd = TimeCurrent() + PeriodSeconds(PERIOD_H1);
        
        ObjectCreate(0, objName, OBJ_RECTANGLE, 0, g_zones[i].time, g_zones[i].priceHigh, timeEnd, g_zones[i].priceLow);
        
        color zoneColor = g_zones[i].isBullish ? clrDarkGreen : clrDarkRed;
        ObjectSetInteger(0, objName, OBJPROP_COLOR, zoneColor);
        ObjectSetInteger(0, objName, OBJPROP_FILL, true);
        ObjectSetInteger(0, objName, OBJPROP_BACK, true);
        ObjectSetInteger(0, objName, OBJPROP_WIDTH, 1);
        ObjectSetString(0, objName, OBJPROP_TEXT, g_zones[i].type);
    }
}
//+------------------------------------------------------------------+
