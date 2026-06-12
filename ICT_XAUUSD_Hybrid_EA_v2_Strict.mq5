//+------------------------------------------------------------------+
//|                                 ICT_XAUUSD_Hybrid_EA_v2_Strict.mq5 |
//|                           IMPROVED VERSION - STRICT FILTERS      |
//|                                         For XAUUSD Trading Only |
//+------------------------------------------------------------------+
#property copyright "ICT XAUUSD Hybrid EA v2.0 - Strict Edition"
#property link      ""
#property version   "2.01"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

//--- Input Parameters
input group "=== Risk Management ==="
input double InpRiskPercent = 0.5;              // Risk % per trade (REDUCED)
input double InpMaxDailyDrawdown = 3.0;         // Max daily drawdown %
input int InpMaxTradesPerSession = 1;           // Max trades per session (REDUCED)
input double InpTPRiskReward = 2.0;             // Take Profit Risk:Reward (INCREASED)
input bool InpUseBreakEven = true;              // Move to break-even at 1R
input int InpMinTradeSpacing = 4;               // Min hours between trades

input group "=== Session Settings (ADJUST FOR YOUR BROKER!) ==="
input int InpAsiaStartHour = 23;                // Asia Start Hour (GMT+YOUR_OFFSET)
input int InpAsiaEndHour = 6;                   // Asia End Hour (GMT+YOUR_OFFSET)
input int InpLondonStartHour = 7;               // London Start Hour (GMT+YOUR_OFFSET)
input int InpLondonEndHour = 11;                // London End Hour (GMT+YOUR_OFFSET)
input string InpGMTOffsetInfo = "GMT+2: Add 2 to hours | GMT-5: Subtract 5"; // Timezone Help

input group "=== ICT Settings (STRICT) ==="
input int InpSwingLookback = 25;                // Swing High/Low lookback (INCREASED)
input int InpOBMinBodyPoints = 80;              // Min OB body size - points (INCREASED)
input double InpFibOTELow = 0.65;               // OTE Fib Low (TIGHTER)
input double InpFibOTEHigh = 0.75;              // OTE Fib High (TIGHTER)
input int InpSLBufferPoints = 15;               // Stop Loss buffer - points (INCREASED)
input int InpMinSweepPoints = 20;               // Min points beyond level for valid sweep

input group "=== Quantitative Filters (STRICT) ==="
input int InpATRPeriod = 14;                    // ATR Period
input double InpATRMinMultiplier = 0.7;         // ATR Min Multiplier (INCREASED)
input double InpATRMaxMultiplier = 1.8;         // ATR Max Multiplier (DECREASED)
input int InpVolumeLookback = 20;               // Volume lookback bars
input double InpVolumeMultiplier = 1.2;         // Volume threshold multiplier (INCREASED)
input double InpConfidenceThreshold = 0.78;     // Min confidence score (INCREASED)
input int InpMaxSpreadPoints = 3000;            // Max spread - points (INCREASED)

input group "=== Structure Confirmation ==="
input bool InpRequireHTFAlignment = true;       // Require H1 structure alignment
input bool InpRequireStrongMSS = true;          // Require strong MSS (not just CHOCH)
input int InpMinImpulsePoints = 150;            // Min impulse size for valid MSS (points)

input group "=== Visualization ==="
input bool InpShowLevels = true;                // Show session levels
input bool InpShowZones = true;                 // Show OB/FVG zones
input bool InpShowLabels = true;                // Show trade labels
input bool InpShowDebugInfo = true;             // Show debug panel

input group "=== Safety ==="
input bool InpEnableCircuitBreaker = true;      // Enable circuit breaker
input bool InpNoTradeFriday = true;             // No trades Friday > 20:00
input int InpMagicNumber = 123457;              // Magic Number

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
    int tradeCount;
};

//--- Trade Zone Structure
struct TradeZone {
    double priceHigh;
    double priceLow;
    datetime time;
    string type;
    bool isBullish;
    bool isValid;
    double strength;
};

//--- Market Structure
struct MarketStructure {
    double lastSwingHigh;
    double lastSwingLow;
    datetime lastHighTime;
    datetime lastLowTime;
    int trend;
    bool mssDetected;
    double mssStrength;
    bool htfAligned;
};

//--- Liquidity Sweep
struct LiquiditySweep {
    bool sweepAbove;
    bool sweepBelow;
    datetime sweepTime;
    double sweepPrice;
    int sweepDirection;
    double sweepDistance;
    bool isValid;
};

//--- Global Variables
SessionData g_previousSession;
SessionData g_currentSession;
MarketStructure g_structure;
LiquiditySweep g_sweep;
TradeZone g_zones[];
double g_startingBalance = 0;
double g_dailyPL = 0;
bool g_tradingEnabled = true;
datetime g_lastBarTime = 0;
datetime g_currentDay = 0;
datetime g_lastTradeTime = 0;

//--- Handles
int g_atrHandle = INVALID_HANDLE;
int g_atrH1Handle = INVALID_HANDLE;

//--- Statistics
int g_totalSignals = 0;
int g_rejectedLowConfidence = 0;
int g_rejectedATR = 0;
int g_rejectedVolume = 0;
int g_rejectedSpread = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    trade.SetExpertMagicNumber(InpMagicNumber);
    trade.SetDeviationInPoints(50);
    trade.SetTypeFilling(GetFillingMode());
    trade.SetAsyncMode(false);
    
    // Initialize ATR
    g_atrHandle = iATR(_Symbol, PERIOD_M5, InpATRPeriod);
    g_atrH1Handle = iATR(_Symbol, PERIOD_H1, InpATRPeriod);
    
    if(g_atrHandle == INVALID_HANDLE || g_atrH1Handle == INVALID_HANDLE) {
        Print("Failed to create ATR indicators");
        return INIT_FAILED;
    }
    
    // Validate symbol
    if(StringFind(_Symbol, "XAU") == -1 && StringFind(_Symbol, "GOLD") == -1) {
        Print("WARNING: Symbol may not be XAUUSD. Current: ", _Symbol);
    }
    
    g_startingBalance = account.Equity();
    g_currentDay = TimeCurrent() - (TimeCurrent() % 86400);

    InitializeStructures();
    
    Print("===========================================");
    Print("ICT XAUUSD Hybrid EA v2.0 STRICT - Initialized");
    Print("===========================================");
    Print("Risk per trade: ", InpRiskPercent, "%");
    Print("Confidence threshold: ", InpConfidenceThreshold);
    Print("Session times: Asia ", InpAsiaStartHour, "-", InpAsiaEndHour, 
          " | London ", InpLondonStartHour, "-", InpLondonEndHour);
    Print("IMPORTANT: Verify session times match your broker GMT offset!");
    Print("===========================================");
    
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
    if(g_atrH1Handle != INVALID_HANDLE) IndicatorRelease(g_atrH1Handle);

    ObjectsDeleteAll(0, "ICT_");
    Comment("");
    
    Print("===========================================");
    Print("EA Statistics:");
    Print("Total signals: ", g_totalSignals);
    Print("Rejected - Low confidence: ", g_rejectedLowConfidence);
    Print("Rejected - ATR filter: ", g_rejectedATR);
    Print("Rejected - Volume filter: ", g_rejectedVolume);
    Print("Rejected - Spread: ", g_rejectedSpread);
    Print("===========================================");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
    datetime currentBarTime = iTime(_Symbol, PERIOD_M5, 0);
    if(currentBarTime == g_lastBarTime) return;
    g_lastBarTime = currentBarTime;
    
    CheckDailyReset();
    UpdateSessionData();
    UpdateMarketStructure();
    DetectLiquiditySweeps();
    UpdateTradeZones();
    ManageOpenPositions();

    if(InpShowLevels) DrawSessionLevels();
    if(InpShowZones) DrawTradeZones();
    if(InpShowDebugInfo) DrawDebugPanel();

    if(!IsTradingAllowed()) return;

    if(g_currentSession.tradeCount < InpMaxTradesPerSession)
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
    g_previousSession.tradeCount = 0;
    
    g_currentSession.high = 0;
    g_currentSession.low = DBL_MAX;
    g_currentSession.isActive = false;
    g_currentSession.tradeCount = 0;
    
    g_structure.trend = 0;
    g_structure.mssDetected = false;
    g_structure.htfAligned = false;
    
    g_sweep.sweepAbove = false;
    g_sweep.sweepBelow = false;
    g_sweep.sweepDirection = 0;
    g_sweep.isValid = false;
    
    ArrayResize(g_zones, 0);
}

//+------------------------------------------------------------------+
//| Check daily reset                                                |
//+------------------------------------------------------------------+
void CheckDailyReset()
{
    datetime todayStart = TimeCurrent() - (TimeCurrent() % 86400);

    if(todayStart != g_currentDay) {
        g_currentDay = todayStart;
        g_startingBalance = account.Equity();
        g_dailyPL = 0;
        g_tradingEnabled = true;
        
        // Reset statistics
        g_totalSignals = 0;
        g_rejectedLowConfidence = 0;
        g_rejectedATR = 0;
        g_rejectedVolume = 0;
        g_rejectedSpread = 0;
        
        Print("═══════════════════════════════════════");
        Print("NEW TRADING DAY | Balance: $", g_startingBalance);
        Print("═══════════════════════════════════════");
    }
    
    if(g_startingBalance <= 0) return;

    // Use equity so floating losses also count toward the daily limit
    g_dailyPL = account.Equity() - g_startingBalance;
    double dailyDrawdownPercent = (g_dailyPL / g_startingBalance) * 100;
    
    if(InpEnableCircuitBreaker && dailyDrawdownPercent <= -InpMaxDailyDrawdown) {
        if(g_tradingEnabled) {
            g_tradingEnabled = false;
            Print("🚨 CIRCUIT BREAKER ACTIVATED! DD: ", dailyDrawdownPercent, "%");
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
    
    bool isAsiaSession = false;
    if(InpAsiaStartHour > InpAsiaEndHour) {
        isAsiaSession = (currentHour >= InpAsiaStartHour || currentHour < InpAsiaEndHour);
    } else {
        isAsiaSession = (currentHour >= InpAsiaStartHour && currentHour < InpAsiaEndHour);
    }
    
    bool isLondonSession = (currentHour >= InpLondonStartHour && currentHour < InpLondonEndHour);
    
    // A new session begins when none was active, or when one session
    // hands over directly to the next (back-to-back configured hours)
    string desiredName = isAsiaSession ? "Asia" : "London";
    bool sessionChange = wasActive && (isAsiaSession || isLondonSession) &&
                         g_currentSession.name != desiredName;

    if(((isAsiaSession || isLondonSession) && !wasActive) || sessionChange) {
        if(g_currentSession.high > 0) {
            g_previousSession = g_currentSession;
            Print("Previous session saved: High=", g_previousSession.high, " Low=", g_previousSession.low);
        }
        
        g_currentSession.high = 0;
        g_currentSession.low = DBL_MAX;
        g_currentSession.isActive = true;
        g_currentSession.name = desiredName;
        g_currentSession.tradeCount = 0;
        
        Print("✓ SESSION STARTED: ", g_currentSession.name, " at ", TimeToString(TimeCurrent()));
    }
    else if(!isAsiaSession && !isLondonSession && wasActive) {
        g_currentSession.isActive = false;
        Print("✓ SESSION ENDED: ", g_currentSession.name);
    }
    
    if(g_currentSession.isActive) {
        double high = iHigh(_Symbol, PERIOD_M5, 1);
        double low = iLow(_Symbol, PERIOD_M5, 1);
        
        if(high > g_currentSession.high) g_currentSession.high = high;
        if(low < g_currentSession.low) g_currentSession.low = low;
        g_currentSession.mid = (g_currentSession.high + g_currentSession.low) / 2;
    }
}

//+------------------------------------------------------------------+
//| Check if trading is allowed                                      |
//+------------------------------------------------------------------+
bool IsTradingAllowed()
{
    if(!g_tradingEnabled) return false;
    if(!g_currentSession.isActive) return false;
    
    // Check minimum trade spacing
    if(g_lastTradeTime > 0) {
        int hoursSinceLastTrade = (int)((TimeCurrent() - g_lastTradeTime) / 3600);
        if(hoursSinceLastTrade < InpMinTradeSpacing) {
            return false;
        }
    }
    
    if(InpNoTradeFriday) {
        MqlDateTime timeStruct;
        TimeToStruct(TimeCurrent(), timeStruct);
        if(timeStruct.day_of_week == 5 && timeStruct.hour >= 20) return false;
    }
    
    long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
    if(spread > InpMaxSpreadPoints) {
        g_rejectedSpread++;
        return false;
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Update market structure                                          |
//+------------------------------------------------------------------+
void UpdateMarketStructure()
{
    int lookback = InpSwingLookback;

    int highestBar = iHighest(_Symbol, PERIOD_M5, MODE_HIGH, lookback, 1);
    int lowestBar = iLowest(_Symbol, PERIOD_M5, MODE_LOW, lookback, 1);
    if(highestBar < 0 || lowestBar < 0) return; // history not loaded yet

    double swingHigh = iHigh(_Symbol, PERIOD_M5, highestBar);
    double swingLow = iLow(_Symbol, PERIOD_M5, lowestBar);

    g_structure.mssDetected = false;
    g_structure.mssStrength = 0;

    // Seed reference levels on the first run so a comparison against
    // zero-initialized values doesn't fire a spurious MSS
    if(g_structure.lastSwingHigh == 0 || g_structure.lastSwingLow == 0) {
        g_structure.lastSwingHigh = swingHigh;
        g_structure.lastSwingLow = swingLow;
        return;
    }
    
    // Check H1 structure for alignment
    if(InpRequireHTFAlignment) {
        double h1High = iHigh(_Symbol, PERIOD_H1, 1);
        double h1Low = iLow(_Symbol, PERIOD_H1, 1);
        double h1PrevHigh = iHigh(_Symbol, PERIOD_H1, 2);
        double h1PrevLow = iLow(_Symbol, PERIOD_H1, 2);
        
        bool h1Bullish = (h1High > h1PrevHigh && h1Low > h1PrevLow);
        bool h1Bearish = (h1Low < h1PrevLow && h1High < h1PrevHigh);
        
        g_structure.htfAligned = h1Bullish || h1Bearish;
    } else {
        g_structure.htfAligned = true;
    }
    
    // Bullish MSS
    if(swingHigh > g_structure.lastSwingHigh && swingLow > g_structure.lastSwingLow) {
        double impulseSize = swingHigh - g_structure.lastSwingLow;
        
        if(InpRequireStrongMSS) {
            if(impulseSize >= InpMinImpulsePoints * _Point) {
                if(g_structure.trend != 1) {
                    g_structure.mssDetected = true;
                    g_structure.trend = 1;
                    g_structure.mssStrength = impulseSize / _Point;
                    Print("✓ BULLISH MSS | Strength: ", (int)g_structure.mssStrength, " points");
                }
            }
        } else {
            if(g_structure.trend != 1) {
                g_structure.mssDetected = true;
                g_structure.trend = 1;
                g_structure.mssStrength = impulseSize / _Point;
            }
        }
    }
    // Bearish MSS
    else if(swingLow < g_structure.lastSwingLow && swingHigh < g_structure.lastSwingHigh) {
        double impulseSize = g_structure.lastSwingHigh - swingLow;
        
        if(InpRequireStrongMSS) {
            if(impulseSize >= InpMinImpulsePoints * _Point) {
                if(g_structure.trend != -1) {
                    g_structure.mssDetected = true;
                    g_structure.trend = -1;
                    g_structure.mssStrength = impulseSize / _Point;
                    Print("✓ BEARISH MSS | Strength: ", (int)g_structure.mssStrength, " points");
                }
            }
        } else {
            if(g_structure.trend != -1) {
                g_structure.mssDetected = true;
                g_structure.trend = -1;
                g_structure.mssStrength = impulseSize / _Point;
            }
        }
    }
    
    g_structure.lastSwingHigh = swingHigh;
    g_structure.lastSwingLow = swingLow;
}

//+------------------------------------------------------------------+
//| Detect liquidity sweeps                                          |
//+------------------------------------------------------------------+
void DetectLiquiditySweeps()
{
    if(g_previousSession.high == 0) return;
    
    double currentHigh = iHigh(_Symbol, PERIOD_M5, 1);
    double currentLow = iLow(_Symbol, PERIOD_M5, 1);
    double currentClose = iClose(_Symbol, PERIOD_M5, 1);
    
    double prevHigh = g_previousSession.high;
    double prevLow = g_previousSession.low;
    
    g_sweep.sweepAbove = false;
    g_sweep.sweepBelow = false;
    g_sweep.isValid = false;
    
    // Sweep above
    if(currentHigh > prevHigh && currentClose < prevHigh) {
        double sweepDistance = (currentHigh - prevHigh) / _Point;
        
        if(sweepDistance >= InpMinSweepPoints) {
            g_sweep.sweepAbove = true;
            g_sweep.sweepDirection = -1;
            g_sweep.sweepPrice = prevHigh;
            g_sweep.sweepTime = iTime(_Symbol, PERIOD_M5, 1);
            g_sweep.sweepDistance = sweepDistance;
            g_sweep.isValid = true;
            Print("🎯 LIQUIDITY SWEEP ABOVE | Distance: ", (int)sweepDistance, " points");
        }
    }
    
    // Sweep below
    if(currentLow < prevLow && currentClose > prevLow) {
        double sweepDistance = (prevLow - currentLow) / _Point;
        
        if(sweepDistance >= InpMinSweepPoints) {
            g_sweep.sweepBelow = true;
            g_sweep.sweepDirection = 1;
            g_sweep.sweepPrice = prevLow;
            g_sweep.sweepTime = iTime(_Symbol, PERIOD_M5, 1);
            g_sweep.sweepDistance = sweepDistance;
            g_sweep.isValid = true;
            Print("🎯 LIQUIDITY SWEEP BELOW | Distance: ", (int)sweepDistance, " points");
        }
    }
}

//+------------------------------------------------------------------+
//| Update trade zones                                               |
//+------------------------------------------------------------------+
void UpdateTradeZones()
{
    ArrayResize(g_zones, 0);
    FindOrderBlocks();
    FindFairValueGaps();
    CalculateOTEZones();
}

//+------------------------------------------------------------------+
//| Find Order Blocks                                                |
//+------------------------------------------------------------------+
void FindOrderBlocks()
{
    for(int i = 2; i < 50; i++) {
        double body = MathAbs(iClose(_Symbol, PERIOD_M5, i) - iOpen(_Symbol, PERIOD_M5, i));
        double nextMove = MathAbs(iClose(_Symbol, PERIOD_M5, i-1) - iOpen(_Symbol, PERIOD_M5, i-1));
        
        if(body < InpOBMinBodyPoints * _Point) continue;
        
        bool isBearishCandle = iClose(_Symbol, PERIOD_M5, i) < iOpen(_Symbol, PERIOD_M5, i);
        bool isBullishImpulse = (iClose(_Symbol, PERIOD_M5, i-1) > iOpen(_Symbol, PERIOD_M5, i-1)) && 
                                nextMove > InpOBMinBodyPoints * _Point;
        
        bool isBullishCandle = iClose(_Symbol, PERIOD_M5, i) > iOpen(_Symbol, PERIOD_M5, i);
        bool isBearishImpulse = (iClose(_Symbol, PERIOD_M5, i-1) < iOpen(_Symbol, PERIOD_M5, i-1)) && 
                                nextMove > InpOBMinBodyPoints * _Point;
        
        if(isBearishCandle && isBullishImpulse) {
            TradeZone zone;
            zone.priceHigh = iHigh(_Symbol, PERIOD_M5, i);
            zone.priceLow = iLow(_Symbol, PERIOD_M5, i);
            zone.time = iTime(_Symbol, PERIOD_M5, i);
            zone.type = "OB";
            zone.isBullish = true;
            zone.isValid = true;
            zone.strength = body / _Point;
            ArrayResize(g_zones, ArraySize(g_zones) + 1);
            g_zones[ArraySize(g_zones) - 1] = zone;
        }
        
        if(isBullishCandle && isBearishImpulse) {
            TradeZone zone;
            zone.priceHigh = iHigh(_Symbol, PERIOD_M5, i);
            zone.priceLow = iLow(_Symbol, PERIOD_M5, i);
            zone.time = iTime(_Symbol, PERIOD_M5, i);
            zone.type = "OB";
            zone.isBullish = false;
            zone.isValid = true;
            zone.strength = body / _Point;
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
        
        if(high1 < low3) {
            double gapSize = (low3 - high1) / _Point;
            if(gapSize >= 30) {
                TradeZone zone;
                zone.priceHigh = low3;
                zone.priceLow = high1;
                zone.time = iTime(_Symbol, PERIOD_M5, i-1);
                zone.type = "FVG";
                zone.isBullish = true;
                zone.isValid = true;
                zone.strength = gapSize;
                ArrayResize(g_zones, ArraySize(g_zones) + 1);
                g_zones[ArraySize(g_zones) - 1] = zone;
            }
        }
        
        if(low1 > high3) {
            double gapSize = (low1 - high3) / _Point;
            if(gapSize >= 30) {
                TradeZone zone;
                zone.priceHigh = low1;
                zone.priceLow = high3;
                zone.time = iTime(_Symbol, PERIOD_M5, i-1);
                zone.type = "FVG";
                zone.isBullish = false;
                zone.isValid = true;
                zone.strength = gapSize;
                ArrayResize(g_zones, ArraySize(g_zones) + 1);
                g_zones[ArraySize(g_zones) - 1] = zone;
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Calculate OTE zones                                              |
//+------------------------------------------------------------------+
void CalculateOTEZones()
{
    if(g_structure.trend == 0) return;
    
    double high = g_structure.lastSwingHigh;
    double low = g_structure.lastSwingLow;
    double range = high - low;
    
    if(g_structure.trend == 1) {
        TradeZone zone;
        zone.priceHigh = low + range * InpFibOTEHigh;
        zone.priceLow = low + range * InpFibOTELow;
        zone.time = TimeCurrent();
        zone.type = "OTE";
        zone.isBullish = true;
        zone.isValid = true;
        zone.strength = range / _Point;
        ArrayResize(g_zones, ArraySize(g_zones) + 1);
        g_zones[ArraySize(g_zones) - 1] = zone;
    }
    else if(g_structure.trend == -1) {
        TradeZone zone;
        zone.priceHigh = high - range * InpFibOTELow;
        zone.priceLow = high - range * InpFibOTEHigh;
        zone.time = TimeCurrent();
        zone.type = "OTE";
        zone.isBullish = false;
        zone.isValid = true;
        zone.strength = range / _Point;
        ArrayResize(g_zones, ArraySize(g_zones) + 1);
        g_zones[ArraySize(g_zones) - 1] = zone;
    }
}

//+------------------------------------------------------------------+
//| Calculate confidence score                                       |
//+------------------------------------------------------------------+
double CalculateConfidenceScore(bool isBuy, string &details)
{
    double score = 0.0;
    details = "Score breakdown: ";
    
    // Liquidity sweep (0.25)
    if((isBuy && g_sweep.sweepBelow && g_sweep.isValid) || 
       (!isBuy && g_sweep.sweepAbove && g_sweep.isValid)) {
        score += 0.25;
        details += "Sweep:0.25 ";
    }
    
    // MSS alignment (0.20)
    if((isBuy && g_structure.trend == 1) || (!isBuy && g_structure.trend == -1)) {
        score += 0.20;
        details += "MSS:0.20 ";
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
    if(confluenceCount >= 2) {
        score += 0.25;
        details += "Confluence:0.25 ";
    } else if(confluenceCount == 1) {
        score += 0.15;
        details += "Zone:0.15 ";
    }
    
    // Volume (0.10)
    if(CheckVolumeFilter()) {
        score += 0.10;
        details += "Vol:0.10 ";
    }
    
    // ATR (0.10)
    if(CheckATRFilter()) {
        score += 0.10;
        details += "ATR:0.10 ";
    }
    
    // HTF alignment (0.10)
    if(g_structure.htfAligned) {
        score += 0.10;
        details += "HTF:0.10 ";
    }
    
    details += "| TOTAL:" + DoubleToString(score, 2);
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
    if(CopyBuffer(g_atrHandle, 0, 1, 20, atr) < 20) return false;

    double currentATR = atr[0];
    double avgATR = 0;
    for(int i = 0; i < 20; i++) avgATR += atr[i];
    avgATR /= 20;
    if(avgATR <= 0) return false;

    double ratio = currentATR / avgATR;
    
    if(ratio >= InpATRMinMultiplier && ratio <= InpATRMaxMultiplier) return true;
    
    g_rejectedATR++;
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
    for(int i = 1; i <= InpVolumeLookback; i++) avgVolume += volumes[i];
    avgVolume /= InpVolumeLookback;

    if(lastClosedVolume >= avgVolume * InpVolumeMultiplier) return true;
    
    g_rejectedVolume++;
    return false;
}

//+------------------------------------------------------------------+
//| Check for entry signal                                           |
//+------------------------------------------------------------------+
void CheckForEntrySignal()
{
    if(SelectOwnPosition()) return;
    
    double currentPrice = iClose(_Symbol, PERIOD_M5, 0);
    
    // Buy setup
    if(g_sweep.sweepBelow && g_sweep.isValid && g_structure.trend == 1) {
        for(int i = 0; i < ArraySize(g_zones); i++) {
            if(g_zones[i].isBullish && g_zones[i].isValid &&
               currentPrice >= g_zones[i].priceLow && 
               currentPrice <= g_zones[i].priceHigh) {
                
                g_totalSignals++;
                string details = "";
                double confidence = CalculateConfidenceScore(true, details);
                
                Print("🔍 BUY SIGNAL | Confidence: ", DoubleToString(confidence, 2), " | ", details);
                
                if(confidence >= InpConfidenceThreshold) {
                    ExecuteBuyTrade(g_zones[i], confidence);
                    return;
                } else {
                    g_rejectedLowConfidence++;
                    Print("❌ REJECTED: Confidence below threshold (", InpConfidenceThreshold, ")");
                }
            }
        }
    }
    
    // Sell setup
    if(g_sweep.sweepAbove && g_sweep.isValid && g_structure.trend == -1) {
        for(int i = 0; i < ArraySize(g_zones); i++) {
            if(!g_zones[i].isBullish && g_zones[i].isValid &&
               currentPrice >= g_zones[i].priceLow && 
               currentPrice <= g_zones[i].priceHigh) {
                
                g_totalSignals++;
                string details = "";
                double confidence = CalculateConfidenceScore(false, details);
                
                Print("🔍 SELL SIGNAL | Confidence: ", DoubleToString(confidence, 2), " | ", details);
                
                if(confidence >= InpConfidenceThreshold) {
                    ExecuteSellTrade(g_zones[i], confidence);
                    return;
                } else {
                    g_rejectedLowConfidence++;
                    Print("❌ REJECTED: Confidence below threshold (", InpConfidenceThreshold, ")");
                }
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Execute buy trade                                                |
//+------------------------------------------------------------------+
void ExecuteBuyTrade(TradeZone &zone, double confidence)
{
    double entryPrice = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    double sl = zone.priceLow - InpSLBufferPoints * _Point;
    double slDistance = entryPrice - sl;
    double minStopDistance = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;

    if(slDistance <= minStopDistance) {
        Print("❌ BUY SKIPPED: SL distance ", DoubleToString(slDistance, _Digits),
              " invalid (price already below zone or inside stops level)");
        return;
    }

    double tp = entryPrice + slDistance * InpTPRiskReward;
    double lotSize = CalculateLotSize(slDistance);

    if(lotSize <= 0) {
        Print("❌ BUY SKIPPED: risk too small for broker minimum lot");
        return;
    }

    if(trade.Buy(lotSize, _Symbol, entryPrice, sl, tp, "ICT BUY | Conf:" + DoubleToString(confidence,2))) {
        g_currentSession.tradeCount++;
        g_lastTradeTime = TimeCurrent();
        
        Print("═══════════════════════════════════════");
        Print("✅ BUY EXECUTED");
        Print("Entry: ", entryPrice, " | SL: ", sl, " | TP: ", tp);
        Print("Lots: ", lotSize, " | RR: ", InpTPRiskReward);
        Print("Zone: ", zone.type, " | Confidence: ", DoubleToString(confidence, 2));
        Print("═══════════════════════════════════════");
        
        if(InpShowLabels) {
            string objName = "ICT_Entry_" + IntegerToString(TimeCurrent());
            ObjectCreate(0, objName, OBJ_ARROW_BUY, 0, TimeCurrent(), entryPrice);
            ObjectSetInteger(0, objName, OBJPROP_COLOR, clrLime);
            ObjectSetInteger(0, objName, OBJPROP_WIDTH, 3);
        }
    } else {
        Print("❌ BUY FAILED: ", trade.ResultRetcodeDescription());
    }
}

//+------------------------------------------------------------------+
//| Execute sell trade                                               |
//+------------------------------------------------------------------+
void ExecuteSellTrade(TradeZone &zone, double confidence)
{
    double entryPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    double sl = zone.priceHigh + InpSLBufferPoints * _Point;
    double slDistance = sl - entryPrice;
    double minStopDistance = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;

    if(slDistance <= minStopDistance) {
        Print("❌ SELL SKIPPED: SL distance ", DoubleToString(slDistance, _Digits),
              " invalid (price already above zone or inside stops level)");
        return;
    }

    double tp = entryPrice - slDistance * InpTPRiskReward;
    double lotSize = CalculateLotSize(slDistance);

    if(lotSize <= 0) {
        Print("❌ SELL SKIPPED: risk too small for broker minimum lot");
        return;
    }

    if(trade.Sell(lotSize, _Symbol, entryPrice, sl, tp, "ICT SELL | Conf:" + DoubleToString(confidence,2))) {
        g_currentSession.tradeCount++;
        g_lastTradeTime = TimeCurrent();
        
        Print("═══════════════════════════════════════");
        Print("✅ SELL EXECUTED");
        Print("Entry: ", entryPrice, " | SL: ", sl, " | TP: ", tp);
        Print("Lots: ", lotSize, " | RR: ", InpTPRiskReward);
        Print("Zone: ", zone.type, " | Confidence: ", DoubleToString(confidence, 2));
        Print("═══════════════════════════════════════");
        
        if(InpShowLabels) {
            string objName = "ICT_Entry_" + IntegerToString(TimeCurrent());
            ObjectCreate(0, objName, OBJ_ARROW_SELL, 0, TimeCurrent(), entryPrice);
            ObjectSetInteger(0, objName, OBJPROP_COLOR, clrRed);
            ObjectSetInteger(0, objName, OBJPROP_WIDTH, 3);
        }
    } else {
        Print("❌ SELL FAILED: ", trade.ResultRetcodeDescription());
    }
}

//+------------------------------------------------------------------+
//| Calculate lot size                                               |
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
    lotSize = MathFloor(lotSize / lotStep) * lotStep;

    // Never round UP to the minimum lot: that would risk more than the
    // configured percentage. Skip the trade instead.
    if(lotSize < minLot) return 0;

    return MathMin(maxLot, lotSize);
}

//+------------------------------------------------------------------+
//| Manage open positions                                            |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
    if(!SelectOwnPosition()) return;

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
    
    if(InpUseBreakEven && slDistance > 0 && profit >= slDistance) {
        if(MathAbs(positionSL - positionOpenPrice) > 10 * _Point) {
            if(trade.PositionModify(ticket, positionOpenPrice, positionTP))
                Print("🔒 Position moved to BREAK-EVEN");
        }
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
//| +------------------------------------------------------------------+
void DrawSessionLevels()
{
    if(g_previousSession.high == 0) return;
    
    string objNameHigh = "ICT_Prev_High";
    if(ObjectFind(0, objNameHigh) == -1) {
        ObjectCreate(0, objNameHigh, OBJ_HLINE, 0, 0, g_previousSession.high);
        ObjectSetInteger(0, objNameHigh, OBJPROP_COLOR, clrRed);
        ObjectSetInteger(0, objNameHigh, OBJPROP_STYLE, STYLE_DASH);
        ObjectSetInteger(0, objNameHigh, OBJPROP_WIDTH, 2);
    } else {
        ObjectSetDouble(0, objNameHigh, OBJPROP_PRICE, g_previousSession.high);
    }
    
    string objNameLow = "ICT_Prev_Low";
    if(ObjectFind(0, objNameLow) == -1) {
        ObjectCreate(0, objNameLow, OBJ_HLINE, 0, 0, g_previousSession.low);
        ObjectSetInteger(0, objNameLow, OBJPROP_COLOR, clrLime);
        ObjectSetInteger(0, objNameLow, OBJPROP_STYLE, STYLE_DASH);
        ObjectSetInteger(0, objNameLow, OBJPROP_WIDTH, 2);
    } else {
        ObjectSetDouble(0, objNameLow, OBJPROP_PRICE, g_previousSession.low);
    }
}

//+------------------------------------------------------------------+
//| Draw trade zones                                                 |
//+------------------------------------------------------------------+
void DrawTradeZones()
{
    for(int i = ObjectsTotal(0, 0, OBJ_RECTANGLE) - 1; i >= 0; i--) {
        string objName = ObjectName(0, i, 0, OBJ_RECTANGLE);
        if(StringFind(objName, "ICT_Zone_") != -1) ObjectDelete(0, objName);
    }
    
    for(int i = 0; i < ArraySize(g_zones) && i < 5; i++) {
        if(!g_zones[i].isValid) continue;
        
        string objName = "ICT_Zone_" + IntegerToString(i);
        datetime timeEnd = TimeCurrent() + PeriodSeconds(PERIOD_H1);
        
        ObjectCreate(0, objName, OBJ_RECTANGLE, 0, g_zones[i].time, g_zones[i].priceHigh, timeEnd, g_zones[i].priceLow);
        
        color zoneColor = g_zones[i].isBullish ? clrDarkGreen : clrDarkRed;
        ObjectSetInteger(0, objName, OBJPROP_COLOR, zoneColor);
        ObjectSetInteger(0, objName, OBJPROP_FILL, true);
        ObjectSetInteger(0, objName, OBJPROP_BACK, true);
        ObjectSetInteger(0, objName, OBJPROP_WIDTH, 1);
    }
}

//+------------------------------------------------------------------+
//| Draw debug panel                                                 |
//+------------------------------------------------------------------+
void DrawDebugPanel()
{
    string info = "";
    info += "═══ ICT EA v2.0 STRICT ═══\n";
    info += "Session: " + g_currentSession.name + "\n";
    info += "Trend: " + (g_structure.trend == 1 ? "BULL" : (g_structure.trend == -1 ? "BEAR" : "NEUTRAL")) + "\n";
    info += "MSS: " + (g_structure.mssDetected ? "YES" : "NO") + "\n";
    info += "Sweep: " + (g_sweep.isValid ? "DETECTED" : "None") + "\n";
    info += "Trades: " + IntegerToString(g_currentSession.tradeCount) + "/" + IntegerToString(InpMaxTradesPerSession) + "\n";
    info += "Daily P/L: $" + DoubleToString(g_dailyPL, 2) + "\n";
    info += "───────────────────\n";
    info += "Signals: " + IntegerToString(g_totalSignals) + "\n";
    info += "Rejected (Conf): " + IntegerToString(g_rejectedLowConfidence) + "\n";
    info += "Rejected (ATR): " + IntegerToString(g_rejectedATR) + "\n";
    info += "Rejected (Vol): " + IntegerToString(g_rejectedVolume) + "\n";

    // OBJ_LABEL cannot render multi-line text; Comment() can
    Comment(info);
}
//+------------------------------------------------------------------+
