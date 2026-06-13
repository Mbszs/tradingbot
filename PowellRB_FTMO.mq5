//+------------------------------------------------------------------+
//|                                              PowellRB_FTMO.mq5    |
//|        Powell-Style Rejection Block (RB) Model — FTMO Compliant   |
//|                                                                   |
//|  STRATEGY OVERVIEW                                                |
//|  ----------------                                                 |
//|  Tracks a configurable set of "key opens" (session-open reference |
//|  prices in New York time). After a key open prints, the EA looks  |
//|  for a Rejection Block (RB): a candle that wicks INTO the level   |
//|  but closes its BODY on the rejection side. The midpoint of that  |
//|  RB box is the Consequent Encroachment (CE) line — the precision  |
//|  entry. A pending limit is placed at CE in the direction of the   |
//|  rejection, SL beyond the wick tip, TP at a fixed R multiple or   |
//|  the next opposing liquidity pool.                                |
//|                                                                   |
//|  NO-REPAINT GUARANTEE                                             |
//|  -------------------                                              |
//|  Key-open capture and RB formation/replacement run ONLY when a    |
//|  reference-timeframe bar has closed. Stored zones use static      |
//|  coordinates and never move. Invalidation may read live price     |
//|  intrabar (to cancel/exit promptly) but never edits historical    |
//|  zone geometry.                                                   |
//|                                                                   |
//|  FTMO GUARDRAILS                                                  |
//|  --------------                                                   |
//|  Per-trade risk %, equity-based daily-loss lockout (persisted     |
//|  across restarts via GlobalVariables), overall max-drawdown hard  |
//|  stop against the initial challenge balance, max trades/day,      |
//|  spread filter, trading-window filter and a manual/scheduled      |
//|  news pause. All values are INPUTS — verify against current FTMO  |
//|  rules and set them yourself; nothing risk-related is hardcoded.  |
//+------------------------------------------------------------------+
#property copyright "PowellRB_FTMO"
#property link      ""
#property version   "1.00"
#property description "Powell-style Rejection Block EA with FTMO risk guardrails (XAUUSD / US100 / NQ, M5-M15)."

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\OrderInfo.mqh>

//==================================================================//
//                            ENUMS                                 //
//==================================================================//
enum ENUM_ENTRY_MODE
{
   ENTRY_CE,            // Limit at CE (50% midpoint) — precision
   ENTRY_BODY_EXTREME   // Limit at body extreme (box top/bottom)
};

enum ENUM_TP_MODE
{
   TP_RR_FIXED,         // Fixed reward:risk multiple
   TP_NEXT_LIQUIDITY    // Nearest opposing swing within lookback
};

//==================================================================//
//                            INPUTS                                //
//==================================================================//
input group "=== General ==="
input ENUM_TIMEFRAMES InpRefTF        = PERIOD_M5;   // Reference timeframe (M5 or M15)
input int    InpBrokerGMTOffset       = 2;           // Broker server offset from GMT (hours, winter)
input bool   InpAutoDST               = true;        // Auto-adjust NY time for US daylight saving
input bool   InpManualNYisDST         = false;       // If AutoDST off: is NY currently on DST?

input group "=== Key Opens (New York time, HH:MM) ==="
input bool   InpKO1_Enable = true;  input string InpKO1_Time = "00:00";  // Midnight open (equilibrium anchor)
input bool   InpKO2_Enable = true;  input string InpKO2_Time = "02:00";  // London open
input bool   InpKO3_Enable = true;  input string InpKO3_Time = "08:30";  // NY macro / news open
input bool   InpKO4_Enable = true;  input string InpKO4_Time = "09:30";  // NY equities open
input bool   InpKO5_Enable = true;  input string InpKO5_Time = "10:00";  // NY AM reversal window
input bool   InpKO6_Enable = false; input string InpKO6_Time = "13:30";  // NY PM open
input bool   InpKO7_Enable = true;  input string InpKO7_Time = "18:00";  // Asia open (equilibrium anchor)

input group "=== RB Detection ==="
input int    InpBodyTolerancePts      = 30;          // Body-overlap tolerance past level (points)
input int    InpMaxActiveZones        = 12;          // Max stored RBs (oldest pruned)
input int    InpMinBoxHeightPts       = 20;          // Reject RB if box height below this (points)

input group "=== Entry ==="
input ENUM_ENTRY_MODE InpEntryMode    = ENTRY_CE;    // Entry trigger reference
input int    InpPendingExpiryBars     = 8;           // Cancel unfilled pending after N ref bars
input int    InpMaxPositions          = 1;           // Concurrent positions (stacking if >1)

input group "=== Filters ==="
input bool   InpUseKillzones          = true;        // Only act on RBs forming inside killzones
input string InpKZ1_Start = "02:00";  input string InpKZ1_End = "05:00"; // London KZ (NY time)
input string InpKZ2_Start = "08:30";  input string InpKZ2_End = "11:00"; // NY AM KZ (NY time)
input bool   InpUseSweep              = false;       // Require liquidity sweep before RB
input int    InpSweepLookback         = 12;          // Swing lookback bars for sweep test
input bool   InpUsePremiumDiscount    = false;       // Bull only in discount / bear only in premium

input group "=== Exits ==="
input ENUM_TP_MODE InpTPMode          = TP_RR_FIXED; // Take-profit mode
input double InpRR                    = 3.0;         // Reward:risk (RR_FIXED) — Powell 1:3 min
input int    InpLiquidityLookback     = 40;          // Opposing-swing lookback (NEXT_LIQUIDITY)
input int    InpSLBufferPts           = 25;          // SL buffer beyond wick tip (points)
input bool   InpUseBreakEven          = true;        // Move SL to BE at +1R
input bool   InpUsePartialClose       = false;       // Close part of position at +1R
input double InpPartialClosePct       = 50.0;        // Percent to close at +1R

input group "=== Risk / FTMO Guardrails ==="
input double InpRiskPercentPerTrade   = 0.5;         // Risk % of equity per trade
input double InpMaxDailyLossPercent    = 4.0;        // Daily loss lockout % (set < FTMO limit)
input double InpMaxOverallDDPercent    = 9.0;        // Overall max DD % (set < FTMO limit)
input double InpInitialBalance        = 100000.0;    // Challenge starting balance (for overall DD)
input int    InpMaxDailyTrades        = 5;           // Max new trades per server day
input int    InpMaxSpreadPts          = 5000;        // Skip entries above this spread (points)
input bool   InpManualNewsPause       = false;       // Manual kill-switch: pause new entries
input string InpNewsTimesServer       = "";          // Optional news times "YYYY.MM.DD HH:MM;..."
input int    InpNewsBlockMinsBefore   = 5;           // Block entries N mins before a news time
input int    InpNewsBlockMinsAfter    = 5;           // Block entries N mins after a news time
input bool   InpUseTradingWindow      = false;       // Restrict trading to a server-time window
input int    InpTradeWindowStartHour  = 0;           // Trading window start (server hour)
input int    InpTradeWindowEndHour    = 24;          // Trading window end (server hour, exclusive)

input group "=== Visuals ==="
input bool   InpShowZones             = true;        // Draw RB boxes
input bool   InpShowCE                = true;        // Draw CE lines
input bool   InpShowKeyOpens          = true;        // Draw key-open levels
input color  InpBullColor             = clrSeaGreen; // Bullish RB colour
input color  InpBearColor             = clrCrimson;  // Bearish RB colour
input color  InpCEColor               = clrGoldenrod;// CE line colour

input group "=== Identity ==="
input long   InpMagicNumber           = 778801;      // Magic number
input string InpComment               = "PowellRB";  // Order comment prefix

//==================================================================//
//                          STRUCTURES                              //
//==================================================================//
struct KeyOpen
{
   string   tag;        // short id, e.g. "0930"
   int      nyHour;     // NY hour
   int      nyMinute;   // NY minute
   bool     enabled;
   double   price;      // open price of the printing candle
   datetime printTime;  // server time the level last printed
   bool     active;     // has printed at least once
};

struct RejectionBlock
{
   int      direction;     // +1 bullish, -1 bearish
   double   level;         // the key-open price it rejected from
   double   boxTop;        // bearish: wick high | bullish: body bottom
   double   boxBottom;     // bearish: body top  | bullish: wick low
   double   ce;            // midpoint (consequent encroachment)
   double   wickExtreme;   // bearish: highest high | bullish: lowest low
   datetime formationTime; // server time of the formation bar
   string   keyOpenTag;
   bool     valid;
   bool     filtersPassed;
   bool     orderPlaced;
   ulong    orderTicket;
   int      ageBars;       // ref bars since the pending order was placed
};

//==================================================================//
//                        GLOBAL STATE                              //
//==================================================================//
CTrade         trade;
COrderInfo     orderInfo;
CPositionInfo  positionInfo;

KeyOpen        g_keyOpens[];
RejectionBlock g_blocks[];

datetime       g_lastRefBarTime = 0;
double         g_dayStartEquity = 0.0;
datetime       g_currentServerDay = 0;
int            g_tradesThisDay = 0;
bool           g_dailyLockout = false;   // daily-loss lockout (resets next day)
bool           g_hardStop     = false;   // overall DD breach (stays until manual reset)
datetime       g_newsTimes[];

string         g_gvPrefix = "";          // GlobalVariable namespace for persistence

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber((ulong)InpMagicNumber);
   trade.SetDeviationInPoints(30);
   trade.SetTypeFilling(GetFillingMode());
   trade.SetAsyncMode(false);

   if(InpRefTF != PERIOD_M5 && InpRefTF != PERIOD_M15)
      Print("WARNING: reference TF is intended to be M5 or M15. Continuing with ", EnumToString(InpRefTF));

   g_gvPrefix = "PowellRB_" + (string)InpMagicNumber + "_" + _Symbol + "_";

   InitKeyOpens();
   ParseNewsTimes();

   // Restore or seed the persisted daily baseline so a mid-day restart
   // does not reset the daily-loss measurement.
   g_currentServerDay = ServerDayStart(TimeCurrent());
   if(!RestoreDailyBaseline())
   {
      g_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      g_tradesThisDay  = 0;
      PersistDailyBaseline();
   }

   g_lastRefBarTime = iTime(_Symbol, InpRefTF, 0);

   PrintFormat("PowellRB_FTMO initialised | RefTF=%s | Risk=%.2f%% | DailyLoss=%.2f%% | MaxDD=%.2f%% | InitBal=%.2f",
               EnumToString(InpRefTF), InpRiskPercentPerTrade, InpMaxDailyLossPercent,
               InpMaxOverallDDPercent, InpInitialBalance);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, "PRB_");
   Comment("");
}

//+------------------------------------------------------------------+
//| Main tick handler                                                |
//+------------------------------------------------------------------+
void OnTick()
{
   // Guardrails and protective logic run every tick.
   RiskGuardrails();
   InvalidateZones();
   ManageOpenPositions();

   // Heavy zone logic runs once per closed reference bar (no repaint).
   datetime refBarTime = iTime(_Symbol, InpRefTF, 0);
   bool newBar = (refBarTime != g_lastRefBarTime);
   if(newBar)
   {
      g_lastRefBarTime = refBarTime;
      AgePendingOrders();      // expire stale pendings
      UpdateKeyOpens();        // capture key-open prices that just printed
      DetectRejectionBlocks(); // form/replace RBs on the last closed bar
      ManageEntries();         // place pending limit for best candidate
   }

   if(InpShowZones || InpShowCE || InpShowKeyOpens)
      Visualize();
}

//==================================================================//
//                      TIME / DST HELPERS                          //
//==================================================================//

//--- Second Sunday of March, 02:00 (approx US DST start)
datetime DSTStart(const int year)
{
   datetime march1 = StringToTime(StringFormat("%04d.03.01 00:00", year));
   MqlDateTime m; TimeToStruct(march1, m);
   int firstSunday = (m.day_of_week == 0) ? 1 : (8 - m.day_of_week);
   int secondSunday = firstSunday + 7;
   return StringToTime(StringFormat("%04d.03.%02d 02:00", year, secondSunday));
}

//--- First Sunday of November, 02:00 (approx US DST end)
datetime DSTEnd(const int year)
{
   datetime nov1 = StringToTime(StringFormat("%04d.11.01 00:00", year));
   MqlDateTime n; TimeToStruct(nov1, n);
   int firstSunday = (n.day_of_week == 0) ? 1 : (8 - n.day_of_week);
   return StringToTime(StringFormat("%04d.11.%02d 02:00", year, firstSunday));
}

//--- Is the given GMT time inside US daylight saving?
//    NOTE: transitions occur at 02:00 LOCAL; comparing against GMT can
//    be off by up to ~1h for the single hour around each switch twice a
//    year. Immaterial for session-open logic; documented for honesty.
bool IsUSDST(const datetime gmt)
{
   if(!InpAutoDST)
      return InpManualNYisDST;
   MqlDateTime t; TimeToStruct(gmt, t);
   return (gmt >= DSTStart(t.year) && gmt < DSTEnd(t.year));
}

//--- NY offset from GMT in seconds (-4h DST, -5h standard)
int NYOffsetSeconds(const datetime gmt)
{
   return IsUSDST(gmt) ? -4 * 3600 : -5 * 3600;
}

//--- Convert broker/server time to New York time
datetime ServerToNY(const datetime serverTime)
{
   datetime gmt = serverTime - (datetime)((long)InpBrokerGMTOffset * 3600);
   return gmt + (datetime)NYOffsetSeconds(gmt);
}

//--- Parse "HH:MM" into hour and minute. Returns false on bad format.
bool ParseHHMM(const string s, int &hour, int &minute)
{
   string parts[];
   if(StringSplit(s, ':', parts) != 2)
      return false;
   hour   = (int)StringToInteger(parts[0]);
   minute = (int)StringToInteger(parts[1]);
   return (hour >= 0 && hour <= 23 && minute >= 0 && minute <= 59);
}

//--- Minutes-since-NY-midnight for a server time
int NYMinutesOfDay(const datetime serverTime)
{
   MqlDateTime t; TimeToStruct(ServerToNY(serverTime), t);
   return t.hour * 60 + t.min;
}

//--- Start of the server day (00:00 server time)
datetime ServerDayStart(const datetime serverTime)
{
   return serverTime - (serverTime % 86400);
}

//==================================================================//
//                     KEY-OPEN MANAGEMENT                          //
//==================================================================//
void InitKeyOpens()
{
   string  tags[]    = {"0000","0200","0830","0930","1000","1330","1800"};
   bool    enabled[] = {InpKO1_Enable,InpKO2_Enable,InpKO3_Enable,InpKO4_Enable,
                        InpKO5_Enable,InpKO6_Enable,InpKO7_Enable};
   string  times[]   = {InpKO1_Time,InpKO2_Time,InpKO3_Time,InpKO4_Time,
                        InpKO5_Time,InpKO6_Time,InpKO7_Time};

   ArrayResize(g_keyOpens, 7);
   for(int i = 0; i < 7; i++)
   {
      int h = 0, m = 0;
      if(!ParseHHMM(times[i], h, m))
      {
         PrintFormat("Bad key-open time '%s' for %s — disabling", times[i], tags[i]);
         enabled[i] = false;
      }
      g_keyOpens[i].tag       = tags[i];
      g_keyOpens[i].nyHour    = h;
      g_keyOpens[i].nyMinute  = m;
      g_keyOpens[i].enabled   = enabled[i];
      g_keyOpens[i].price     = 0.0;
      g_keyOpens[i].printTime = 0;
      g_keyOpens[i].active    = false;
   }
}

//--- Capture a key-open price the moment its candle prints. Evaluated on
//    the just-opened bar (shift 0); a bar's OPEN price is fixed at open
//    and never repaints. When a key open re-prints, its RB is cleared.
void UpdateKeyOpens()
{
   datetime barTime = iTime(_Symbol, InpRefTF, 0);
   MqlDateTime ny; TimeToStruct(ServerToNY(barTime), ny);

   for(int i = 0; i < ArraySize(g_keyOpens); i++)
   {
      if(!g_keyOpens[i].enabled)
         continue;
      if(ny.hour == g_keyOpens[i].nyHour && ny.min == g_keyOpens[i].nyMinute)
      {
         if(g_keyOpens[i].printTime == barTime)
            continue; // already captured this instance
         g_keyOpens[i].price     = iOpen(_Symbol, InpRefTF, 0);
         g_keyOpens[i].printTime = barTime;
         g_keyOpens[i].active    = true;
         ClearBlocksForLevel(g_keyOpens[i].tag);   // reset tracking on new instance
         PrintFormat("Key open %s printed @ %.5f (%02d:%02d NY)",
                     g_keyOpens[i].tag, g_keyOpens[i].price, ny.hour, ny.min);
      }
   }
}

//--- Premium(+1) / Discount(-1) / Unknown(0) vs the 00:00 & 18:00 opens
int PremiumDiscountState(const double price)
{
   double a = GetKeyOpenPrice("0000");
   double b = GetKeyOpenPrice("1800");
   double eq = 0.0; int n = 0;
   if(a > 0) { eq += a; n++; }
   if(b > 0) { eq += b; n++; }
   if(n == 0)
      return 0;
   eq /= n;
   return (price > eq) ? 1 : -1;
}

double GetKeyOpenPrice(const string tag)
{
   for(int i = 0; i < ArraySize(g_keyOpens); i++)
      if(g_keyOpens[i].tag == tag && g_keyOpens[i].active)
         return g_keyOpens[i].price;
   return 0.0;
}

bool IsKeyOpenActive(const string tag)
{
   for(int i = 0; i < ArraySize(g_keyOpens); i++)
      if(g_keyOpens[i].tag == tag)
         return g_keyOpens[i].active;
   return false;
}

//==================================================================//
//                  REJECTION BLOCK DETECTION                       //
//==================================================================//

//--- Examine the last CLOSED bar (shift 1) for a rejection off each
//    active key open. Keep only the most extreme wick per level.
void DetectRejectionBlocks()
{
   int shift = 1;
   double hi = iHigh (_Symbol, InpRefTF, shift);
   double lo = iLow  (_Symbol, InpRefTF, shift);
   double op = iOpen (_Symbol, InpRefTF, shift);
   double cl = iClose(_Symbol, InpRefTF, shift);
   if(hi <= 0 || lo <= 0)
      return;

   datetime barTime = iTime(_Symbol, InpRefTF, shift);
   double   tol      = InpBodyTolerancePts * _Point;
   double   bodyTop  = MathMax(op, cl);
   double   bodyBot  = MathMin(op, cl);

   for(int i = 0; i < ArraySize(g_keyOpens); i++)
   {
      if(!g_keyOpens[i].enabled || !g_keyOpens[i].active)
         continue;
      double level = g_keyOpens[i].price;
      // Only consider bars at/after the key open printed.
      if(barTime < g_keyOpens[i].printTime)
         continue;

      //--- Bearish RB: upper wick reaches/crosses level, body stays below
      if(hi >= level && bodyTop <= level + tol && cl < level)
      {
         double bt = hi;            // box top  = wick tip
         double bb = bodyTop;       // box bottom = body top
         if((bt - bb) >= InpMinBoxHeightPts * _Point)
            RegisterOrReplaceRB(-1, g_keyOpens[i].tag, level, bt, bb, hi, barTime);
      }

      //--- Bullish RB: lower wick reaches/crosses level, body stays above
      if(lo <= level && bodyBot >= level - tol && cl > level)
      {
         double bb = lo;            // box bottom = wick tip
         double bt = bodyBot;       // box top    = body bottom
         if((bt - bb) >= InpMinBoxHeightPts * _Point)
            RegisterOrReplaceRB(+1, g_keyOpens[i].tag, level, bt, bb, lo, barTime);
      }
   }
}

//--- Insert a new RB for a level, or replace the existing one if this
//    wick is "better" (higher for bearish, lower for bullish).
void RegisterOrReplaceRB(const int direction, const string tag, const double level,
                         const double boxTop, const double boxBottom,
                         const double wickExtreme, const datetime formationTime)
{
   int existing = -1;
   for(int i = 0; i < ArraySize(g_blocks); i++)
   {
      if(g_blocks[i].keyOpenTag == tag && g_blocks[i].direction == direction && g_blocks[i].valid)
      {
         existing = i;
         break;
      }
   }

   if(existing >= 0)
   {
      // Do not disturb a zone that already has a working/filled order.
      if(g_blocks[existing].orderPlaced)
         return;
      bool better = (direction == -1) ? (wickExtreme > g_blocks[existing].wickExtreme)
                                       : (wickExtreme < g_blocks[existing].wickExtreme);
      if(!better)
         return;
   }

   RejectionBlock rb;
   rb.direction     = direction;
   rb.level         = level;
   rb.boxTop        = boxTop;
   rb.boxBottom     = boxBottom;
   rb.ce            = (boxTop + boxBottom) / 2.0;
   rb.wickExtreme   = wickExtreme;
   rb.formationTime = formationTime;
   rb.keyOpenTag    = tag;
   rb.valid         = true;
   rb.orderPlaced   = false;
   rb.orderTicket   = 0;
   rb.ageBars       = 0;
   rb.filtersPassed = PassesFilters(rb);

   if(existing >= 0)
   {
      g_blocks[existing] = rb;
   }
   else
   {
      int n = ArraySize(g_blocks);
      ArrayResize(g_blocks, n + 1);
      g_blocks[n] = rb;
      PruneZones();
   }

   PrintFormat("RB %s formed | tag=%s | level=%.5f | CE=%.5f | box[%.5f..%.5f] | filters=%s",
               (direction == 1 ? "BULL" : "BEAR"), tag, level, rb.ce, boxTop, boxBottom,
               (rb.filtersPassed ? "PASS" : "fail"));
}

//--- Keep the array within MaxActiveZones, dropping the oldest that has
//    no live order attached.
void PruneZones()
{
   while(ArraySize(g_blocks) > InpMaxActiveZones)
   {
      int oldest = -1;
      datetime oldestTime = 0;
      for(int i = 0; i < ArraySize(g_blocks); i++)
      {
         if(g_blocks[i].orderPlaced)
            continue;
         if(oldest == -1 || g_blocks[i].formationTime < oldestTime)
         {
            oldest = i;
            oldestTime = g_blocks[i].formationTime;
         }
      }
      if(oldest == -1)
         break; // every zone has a live order; leave them be
      RemoveBlockAt(oldest);
   }
}

void ClearBlocksForLevel(const string tag)
{
   for(int i = ArraySize(g_blocks) - 1; i >= 0; i--)
   {
      if(g_blocks[i].keyOpenTag != tag)
         continue;
      if(g_blocks[i].orderPlaced)
         CancelPending(g_blocks[i]);
      RemoveBlockAt(i);
   }
}

void RemoveBlockAt(const int idx)
{
   int n = ArraySize(g_blocks);
   if(idx < 0 || idx >= n)
      return;
   DeleteZoneObjects(g_blocks[idx]);
   for(int i = idx; i < n - 1; i++)
      g_blocks[i] = g_blocks[i + 1];
   ArrayResize(g_blocks, n - 1);
}

//==================================================================//
//                        INVALIDATION                              //
//==================================================================//

//--- Remove any RB whose tip has been traded through. Checked intrabar
//    on live price so a dead zone is dropped (and its pending cancelled)
//    immediately, but zone geometry is never edited.
void InvalidateZones()
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   for(int i = ArraySize(g_blocks) - 1; i >= 0; i--)
   {
      if(!g_blocks[i].valid)
      {
         RemoveBlockAt(i);
         continue;
      }
      bool dead = false;
      if(g_blocks[i].direction == -1 && ask > g_blocks[i].boxTop)      // bearish tip = box top
         dead = true;
      else if(g_blocks[i].direction == 1 && bid < g_blocks[i].boxBottom) // bullish tip = box bottom
         dead = true;

      if(dead)
      {
         if(g_blocks[i].orderPlaced)
            CancelPending(g_blocks[i]);
         PrintFormat("RB invalidated (tip traded through) | tag=%s dir=%d",
                     g_blocks[i].keyOpenTag, g_blocks[i].direction);
         RemoveBlockAt(i);
      }
   }
}

//==================================================================//
//                           FILTERS                                //
//==================================================================//
bool PassesFilters(const RejectionBlock &rb)
{
   // Killzone: the RB's formation bar must fall inside an enabled window.
   if(InpUseKillzones && !InKillzone(rb.formationTime))
      return false;

   // Premium/Discount: bullish only in discount, bearish only in premium.
   if(InpUsePremiumDiscount)
   {
      int pd = PremiumDiscountState(rb.ce);
      if(pd == 0)
         return false; // anchors not yet known
      if(rb.direction == 1 && pd != -1)
         return false;
      if(rb.direction == -1 && pd != 1)
         return false;
   }

   // Liquidity sweep: formation bar must have swept the recent extreme.
   if(InpUseSweep && !SweptLiquidity(rb.direction))
      return false;

   return true;
}

bool InKillzone(const datetime serverTime)
{
   int mins = NYMinutesOfDay(serverTime);
   if(InWindowMinutes(mins, InpKZ1_Start, InpKZ1_End))
      return true;
   if(InWindowMinutes(mins, InpKZ2_Start, InpKZ2_End))
      return true;
   return false;
}

bool InWindowMinutes(const int mins, const string startStr, const string endStr)
{
   int sh, sm, eh, em;
   if(!ParseHHMM(startStr, sh, sm) || !ParseHHMM(endStr, eh, em))
      return false;
   int start = sh * 60 + sm;
   int end   = eh * 60 + em;
   if(start <= end)
      return (mins >= start && mins < end);
   // window crosses midnight
   return (mins >= start || mins < end);
}

//--- The formation bar (shift 1) swept the recent swing: bearish RB needs
//    a buy-side sweep (high above prior highs); bullish needs a sell-side
//    sweep (low below prior lows). Uses closed bars only.
bool SweptLiquidity(const int direction)
{
   int look = InpSweepLookback;
   if(look < 2)
      return true;
   double formHigh = iHigh(_Symbol, InpRefTF, 1);
   double formLow  = iLow (_Symbol, InpRefTF, 1);

   int hh = iHighest(_Symbol, InpRefTF, MODE_HIGH, look, 2);
   int ll = iLowest (_Symbol, InpRefTF, MODE_LOW,  look, 2);
   if(hh < 0 || ll < 0)
      return false;

   double priorHigh = iHigh(_Symbol, InpRefTF, hh);
   double priorLow  = iLow (_Symbol, InpRefTF, ll);

   if(direction == -1)
      return (formHigh > priorHigh);  // swept buy-side liquidity
   return (formLow < priorLow);       // swept sell-side liquidity
}

//==================================================================//
//                      ENTRY MANAGEMENT                            //
//==================================================================//

//--- Place a pending limit for the newest valid, filter-passing RB that
//    has no order yet, provided guardrails and position caps allow it.
void ManageEntries()
{
   if(g_hardStop || g_dailyLockout)
      return;
   if(!TradingWindowOpen())
      return;
   if(NewsBlocked())
      return;
   if(InpManualNewsPause)
      return;
   if(g_tradesThisDay >= InpMaxDailyTrades)
      return;

   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > InpMaxSpreadPts)
      return;

   int openPositions = CountOwnPositions();
   int workingOrders = CountOwnOrders();
   if(openPositions + workingOrders >= InpMaxPositions)
      return;

   // Pick the most recently formed qualifying RB without an order.
   int best = -1;
   datetime newest = 0;
   for(int i = 0; i < ArraySize(g_blocks); i++)
   {
      if(!g_blocks[i].valid || !g_blocks[i].filtersPassed || g_blocks[i].orderPlaced)
         continue;
      if(best == -1 || g_blocks[i].formationTime > newest)
      {
         best = i;
         newest = g_blocks[i].formationTime;
      }
   }
   if(best == -1)
      return;

   PlacePendingForBlock(best);
}

void PlacePendingForBlock(const int idx)
{
   RejectionBlock rb = g_blocks[idx];

   double entry = (InpEntryMode == ENTRY_CE)
                    ? rb.ce
                    : (rb.direction == -1 ? rb.boxTop : rb.boxBottom);
   entry = NormalizeDouble(entry, _Digits);

   double buffer = InpSLBufferPts * _Point;
   double sl, tp, riskDist;

   if(rb.direction == -1) // bearish → sell limit above
   {
      sl = NormalizeDouble(rb.boxTop + buffer, _Digits);
      riskDist = sl - entry;
      if(riskDist <= 0)
      {
         PrintFormat("Skip bearish %s: non-positive risk distance", rb.keyOpenTag);
         return;
      }
      tp = ComputeTP(rb.direction, entry, riskDist);
      // For a sell limit, market must be below the entry price.
      if(SymbolInfoDouble(_Symbol, SYMBOL_BID) >= entry)
         return;
   }
   else                   // bullish → buy limit below
   {
      sl = NormalizeDouble(rb.boxBottom - buffer, _Digits);
      riskDist = entry - sl;
      if(riskDist <= 0)
      {
         PrintFormat("Skip bullish %s: non-positive risk distance", rb.keyOpenTag);
         return;
      }
      tp = ComputeTP(rb.direction, entry, riskDist);
      if(SymbolInfoDouble(_Symbol, SYMBOL_ASK) <= entry)
         return;
   }

   // Respect the broker minimum stop distance.
   double minStop = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   if(riskDist <= minStop)
   {
      PrintFormat("Skip %s: risk distance %.5f below stops level %.5f", rb.keyOpenTag, riskDist, minStop);
      return;
   }

   double lots = CalcLotsByRisk(riskDist);
   if(lots <= 0)
   {
      PrintFormat("Skip %s: lot size below broker minimum for configured risk", rb.keyOpenTag);
      return;
   }

   string cmt = StringFormat("%s|%s|RR%.1f", InpComment, rb.keyOpenTag, InpRR);
   bool ok = false;
   ResetLastError();
   if(rb.direction == -1)
      ok = trade.SellLimit(lots, entry, _Symbol, sl, tp, ORDER_TIME_GTC, 0, cmt);
   else
      ok = trade.BuyLimit(lots, entry, _Symbol, sl, tp, ORDER_TIME_GTC, 0, cmt);

   // One retry on requote/price-change.
   if(!ok && (trade.ResultRetcode() == TRADE_RETCODE_REQUOTE ||
              trade.ResultRetcode() == TRADE_RETCODE_PRICE_CHANGED))
   {
      if(rb.direction == -1)
         ok = trade.SellLimit(lots, entry, _Symbol, sl, tp, ORDER_TIME_GTC, 0, cmt);
      else
         ok = trade.BuyLimit(lots, entry, _Symbol, sl, tp, ORDER_TIME_GTC, 0, cmt);
   }

   if(ok)
   {
      g_blocks[idx].orderPlaced = true;
      g_blocks[idx].orderTicket = trade.ResultOrder();
      g_blocks[idx].ageBars     = 0;
      PrintFormat("PENDING %s %s | entry=%.5f SL=%.5f TP=%.5f lots=%.2f RR=%.1f risk=%.2f%%",
                  (rb.direction == 1 ? "BUYLIMIT" : "SELLLIMIT"), rb.keyOpenTag,
                  entry, sl, tp, lots, InpRR, InpRiskPercentPerTrade);
   }
   else
   {
      PrintFormat("Pending failed %s: %d %s", rb.keyOpenTag,
                  trade.ResultRetcode(), trade.ResultRetcodeDescription());
   }
}

//--- TP from RR multiple or nearest opposing liquidity.
double ComputeTP(const int direction, const double entry, const double riskDist)
{
   if(InpTPMode == TP_RR_FIXED)
   {
      double tp = (direction == -1) ? entry - InpRR * riskDist
                                    : entry + InpRR * riskDist;
      return NormalizeDouble(tp, _Digits);
   }

   // NEXT_LIQUIDITY: opposing swing extreme within lookback (closed bars).
   int look = InpLiquidityLookback;
   if(direction == -1)
   {
      int ll = iLowest(_Symbol, InpRefTF, MODE_LOW, look, 1);
      double target = (ll >= 0) ? iLow(_Symbol, InpRefTF, ll) : entry - InpRR * riskDist;
      if(target >= entry) // no liquidity below — fall back to RR
         target = entry - InpRR * riskDist;
      return NormalizeDouble(target, _Digits);
   }
   else
   {
      int hh = iHighest(_Symbol, InpRefTF, MODE_HIGH, look, 1);
      double target = (hh >= 0) ? iHigh(_Symbol, InpRefTF, hh) : entry + InpRR * riskDist;
      if(target <= entry)
         target = entry + InpRR * riskDist;
      return NormalizeDouble(target, _Digits);
   }
}

//--- Age working pendings; cancel those unfilled past the expiry.
void AgePendingOrders()
{
   for(int i = 0; i < ArraySize(g_blocks); i++)
   {
      if(!g_blocks[i].orderPlaced)
         continue;
      // If the order is gone (filled or cancelled), clear the flag.
      if(!orderInfo.Select(g_blocks[i].orderTicket))
      {
         g_blocks[i].orderPlaced = false;
         g_blocks[i].orderTicket = 0;
         continue;
      }
      g_blocks[i].ageBars++;
      if(g_blocks[i].ageBars >= InpPendingExpiryBars)
      {
         CancelPending(g_blocks[i]);
         PrintFormat("Pending expired (%d bars) | tag=%s", g_blocks[i].ageBars, g_blocks[i].keyOpenTag);
      }
   }
}

void CancelPending(RejectionBlock &rb)
{
   if(rb.orderTicket != 0 && orderInfo.Select(rb.orderTicket))
      trade.OrderDelete(rb.orderTicket);
   rb.orderPlaced = false;
   rb.orderTicket = 0;
}

//==================================================================//
//                   OPEN POSITION MANAGEMENT                       //
//==================================================================//

//--- Break-even and partial close at +1R for our own positions.
void ManageOpenPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !positionInfo.SelectByTicket(ticket))
         continue;
      if(positionInfo.Symbol() != _Symbol || positionInfo.Magic() != InpMagicNumber)
         continue;

      double openPrice = positionInfo.PriceOpen();
      double sl        = positionInfo.StopLoss();
      double tp        = positionInfo.TakeProfit();
      long   type      = positionInfo.PositionType();
      double price     = (type == POSITION_TYPE_BUY)
                           ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                           : SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      double riskDist = MathAbs(openPrice - sl);
      if(riskDist <= 0)
         continue;
      double profitDist = (type == POSITION_TYPE_BUY) ? (price - openPrice)
                                                      : (openPrice - price);
      if(profitDist < riskDist) // below +1R: nothing to do
         continue;
      if(!InpUseBreakEven && !InpUsePartialClose) // both management options off
         continue;

      // At/above +1R. Do the partial once (if enabled), then always pull
      // the stop to break-even — that BE flag is also what prevents the
      // partial from re-firing on subsequent ticks.
      if(AtBreakEven(type, sl, openPrice))
         continue; // already handled this position at +1R

      if(InpUsePartialClose)
      {
         double vol     = positionInfo.Volume();
         double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
         double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
         double part    = MathFloor(vol * (InpPartialClosePct / 100.0) / lotStep) * lotStep;
         if(part >= minLot && part < vol)
            trade.PositionClosePartial(ticket, part);
      }

      // Move to break-even (and mark this position as handled).
      double be = NormalizeDouble(openPrice, _Digits);
      if(trade.PositionModify(ticket, be, tp))
         PrintFormat("BE set | ticket=%I64u", ticket);
   }
}

bool AtBreakEven(const long type, const double sl, const double openPrice)
{
   double tolerance = 2 * _Point;
   if(type == POSITION_TYPE_BUY)
      return (sl >= openPrice - tolerance);
   return (sl <= openPrice + tolerance);
}

//==================================================================//
//                      RISK GUARDRAILS                             //
//==================================================================//
void RiskGuardrails()
{
   // Roll the day baseline at server midnight.
   datetime today = ServerDayStart(TimeCurrent());
   if(today != g_currentServerDay)
   {
      g_currentServerDay = today;
      g_dayStartEquity   = AccountInfoDouble(ACCOUNT_EQUITY);
      g_tradesThisDay    = 0;
      g_dailyLockout     = false;
      PersistDailyBaseline();
      PrintFormat("New server day | baseline equity=%.2f", g_dayStartEquity);
   }

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);

   // Overall max drawdown vs the challenge starting balance — hard stop.
   if(InpInitialBalance > 0)
   {
      double ddPct = (InpInitialBalance - equity) / InpInitialBalance * 100.0;
      if(ddPct >= InpMaxOverallDDPercent && !g_hardStop)
      {
         g_hardStop = true;
         Print("HARD STOP: overall max drawdown breached (", DoubleToString(ddPct, 2), "%) — closing all");
         CloseAllOwn();
         CancelAllOwnPendings();
      }
   }

   // Equity-based daily loss — lockout until next server day.
   if(g_dayStartEquity > 0)
   {
      double dayLossPct = (g_dayStartEquity - equity) / g_dayStartEquity * 100.0;
      if(dayLossPct >= InpMaxDailyLossPercent && !g_dailyLockout)
      {
         g_dailyLockout = true;
         Print("DAILY LOCKOUT: daily loss breached (", DoubleToString(dayLossPct, 2), "%) — closing all");
         CloseAllOwn();
         CancelAllOwnPendings();
      }
   }
}

bool TradingWindowOpen()
{
   if(!InpUseTradingWindow)
      return true;
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   if(InpTradeWindowStartHour <= InpTradeWindowEndHour)
      return (t.hour >= InpTradeWindowStartHour && t.hour < InpTradeWindowEndHour);
   return (t.hour >= InpTradeWindowStartHour || t.hour < InpTradeWindowEndHour);
}

void ParseNewsTimes()
{
   ArrayResize(g_newsTimes, 0);
   if(StringLen(InpNewsTimesServer) == 0)
      return;
   string items[];
   int n = StringSplit(InpNewsTimesServer, ';', items);
   for(int i = 0; i < n; i++)
   {
      string s = items[i];
      StringTrimLeft(s);
      StringTrimRight(s);
      if(StringLen(s) == 0)
         continue;
      datetime t = StringToTime(s);
      if(t > 0)
      {
         int m = ArraySize(g_newsTimes);
         ArrayResize(g_newsTimes, m + 1);
         g_newsTimes[m] = t;
      }
   }
   PrintFormat("Parsed %d scheduled news time(s)", ArraySize(g_newsTimes));
}

bool NewsBlocked()
{
   if(ArraySize(g_newsTimes) == 0)
      return false;
   datetime now = TimeCurrent();
   for(int i = 0; i < ArraySize(g_newsTimes); i++)
   {
      datetime from = g_newsTimes[i] - (datetime)(InpNewsBlockMinsBefore * 60);
      datetime to   = g_newsTimes[i] + (datetime)(InpNewsBlockMinsAfter * 60);
      if(now >= from && now <= to)
         return true;
   }
   return false;
}

//==================================================================//
//                  SIZING / ACCOUNT HELPERS                        //
//==================================================================//
double CalcLotsByRisk(const double riskDistPrice)
{
   double equity     = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskAmount = equity * (InpRiskPercentPerTrade / 100.0);

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double minLot    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   if(riskDistPrice <= 0 || tickValue <= 0 || tickSize <= 0 || lotStep <= 0)
      return 0.0;

   double lossPerLot = (riskDistPrice / tickSize) * tickValue;
   if(lossPerLot <= 0)
      return 0.0;

   double lots = riskAmount / lossPerLot;
   lots = MathFloor(lots / lotStep) * lotStep;

   // Never round UP to the minimum: that would exceed the configured
   // risk. Skip the trade instead.
   if(lots < minLot)
      return 0.0;
   return MathMin(maxLot, lots);
}

int CountOwnPositions()
{
   int c = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !positionInfo.SelectByTicket(ticket))
         continue;
      if(positionInfo.Symbol() == _Symbol && positionInfo.Magic() == InpMagicNumber)
         c++;
   }
   return c;
}

int CountOwnOrders()
{
   int c = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0 || !orderInfo.Select(ticket))
         continue;
      if(orderInfo.Symbol() == _Symbol && orderInfo.Magic() == InpMagicNumber)
         c++;
   }
   return c;
}

void CloseAllOwn()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !positionInfo.SelectByTicket(ticket))
         continue;
      if(positionInfo.Symbol() == _Symbol && positionInfo.Magic() == InpMagicNumber)
         trade.PositionClose(ticket);
   }
}

void CancelAllOwnPendings()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0 || !orderInfo.Select(ticket))
         continue;
      if(orderInfo.Symbol() == _Symbol && orderInfo.Magic() == InpMagicNumber)
         trade.OrderDelete(ticket);
   }
   for(int i = 0; i < ArraySize(g_blocks); i++)
   {
      g_blocks[i].orderPlaced = false;
      g_blocks[i].orderTicket = 0;
   }
}

ENUM_ORDER_TYPE_FILLING GetFillingMode()
{
   long filling = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_FOK) != 0) return ORDER_FILLING_FOK;
   if((filling & SYMBOL_FILLING_IOC) != 0) return ORDER_FILLING_IOC;
   return ORDER_FILLING_RETURN;
}

//==================================================================//
//             DAILY BASELINE PERSISTENCE (RESTART-SAFE)            //
//==================================================================//
void PersistDailyBaseline()
{
   GlobalVariableSet(g_gvPrefix + "day",    (double)g_currentServerDay);
   GlobalVariableSet(g_gvPrefix + "equity", g_dayStartEquity);
   GlobalVariableSet(g_gvPrefix + "trades", (double)g_tradesThisDay);
}

//--- Returns true if a baseline for *today* was restored.
bool RestoreDailyBaseline()
{
   if(!GlobalVariableCheck(g_gvPrefix + "day"))
      return false;
   datetime storedDay = (datetime)GlobalVariableGet(g_gvPrefix + "day");
   if(ServerDayStart(storedDay) != g_currentServerDay)
      return false;
   g_dayStartEquity = GlobalVariableGet(g_gvPrefix + "equity");
   g_tradesThisDay  = (int)GlobalVariableGet(g_gvPrefix + "trades");
   if(g_dayStartEquity <= 0)
      return false;
   PrintFormat("Restored daily baseline | equity=%.2f trades=%d", g_dayStartEquity, g_tradesThisDay);
   return true;
}

//==================================================================//
//                     TRADE EVENT TRACKING                         //
//==================================================================//

//--- Count a filled entry toward the daily cap when a pending becomes a
//    position (deal added on this symbol+magic).
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest      &request,
                        const MqlTradeResult       &result)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD)
      return;
   if(!HistoryDealSelect(trans.deal))
      return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol)
      return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagicNumber)
      return;
   if(HistoryDealGetInteger(trans.deal, DEAL_ENTRY) != DEAL_ENTRY_IN)
      return;

   g_tradesThisDay++;
   PersistDailyBaseline();
   PrintFormat("Entry filled | trades today=%d/%d", g_tradesThisDay, InpMaxDailyTrades);
}

//==================================================================//
//                        VISUALIZATION                             //
//==================================================================//
void Visualize()
{
   // Key-open horizontal levels.
   if(InpShowKeyOpens)
   {
      for(int i = 0; i < ArraySize(g_keyOpens); i++)
      {
         string nm = "PRB_KO_" + g_keyOpens[i].tag;
         if(!g_keyOpens[i].active)
         {
            if(ObjectFind(0, nm) >= 0) ObjectDelete(0, nm);
            continue;
         }
         if(ObjectFind(0, nm) < 0)
         {
            ObjectCreate(0, nm, OBJ_HLINE, 0, 0, g_keyOpens[i].price);
            ObjectSetInteger(0, nm, OBJPROP_COLOR, clrSlateGray);
            ObjectSetInteger(0, nm, OBJPROP_STYLE, STYLE_DOT);
            ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
            ObjectSetString (0, nm, OBJPROP_TOOLTIP, "KO " + g_keyOpens[i].tag);
         }
         else
         {
            ObjectSetDouble(0, nm, OBJPROP_PRICE, g_keyOpens[i].price);
         }
      }
   }

   // RB boxes and CE lines (static coordinates — never drift).
   for(int i = 0; i < ArraySize(g_blocks); i++)
   {
      string id = StringFormat("%s_%d_%I64d", g_blocks[i].keyOpenTag,
                               g_blocks[i].direction, (long)g_blocks[i].formationTime);
      datetime t1 = g_blocks[i].formationTime;
      datetime t2 = t1 + (datetime)(PeriodSeconds(InpRefTF) * 24);

      if(InpShowZones)
      {
         string boxNm = "PRB_BOX_" + id;
         if(ObjectFind(0, boxNm) < 0)
         {
            ObjectCreate(0, boxNm, OBJ_RECTANGLE, 0, t1, g_blocks[i].boxTop, t2, g_blocks[i].boxBottom);
            color c = (g_blocks[i].direction == 1) ? InpBullColor : InpBearColor;
            ObjectSetInteger(0, boxNm, OBJPROP_COLOR, c);
            ObjectSetInteger(0, boxNm, OBJPROP_BACK, true);
            ObjectSetInteger(0, boxNm, OBJPROP_FILL, true);
            ObjectSetInteger(0, boxNm, OBJPROP_WIDTH, 1);
         }
      }

      if(InpShowCE)
      {
         string ceNm = "PRB_CE_" + id;
         if(ObjectFind(0, ceNm) < 0)
         {
            ObjectCreate(0, ceNm, OBJ_TREND, 0, t1, g_blocks[i].ce, t2, g_blocks[i].ce);
            ObjectSetInteger(0, ceNm, OBJPROP_COLOR, InpCEColor);
            ObjectSetInteger(0, ceNm, OBJPROP_STYLE, STYLE_DASH);
            ObjectSetInteger(0, ceNm, OBJPROP_WIDTH, 1);
            ObjectSetInteger(0, ceNm, OBJPROP_RAY_RIGHT, false);
         }
      }
   }

   // Status panel.
   string status = StringFormat("PowellRB_FTMO  |  zones:%d  trades:%d/%d  %s%s%s",
                     ArraySize(g_blocks), g_tradesThisDay, InpMaxDailyTrades,
                     (g_dailyLockout ? "[DAILY LOCKOUT] " : ""),
                     (g_hardStop ? "[HARD STOP] " : ""),
                     (InpManualNewsPause ? "[NEWS PAUSE]" : ""));
   Comment(status);
}

void DeleteZoneObjects(const RejectionBlock &rb)
{
   string id = StringFormat("%s_%d_%I64d", rb.keyOpenTag, rb.direction, (long)rb.formationTime);
   string boxNm = "PRB_BOX_" + id;
   string ceNm  = "PRB_CE_"  + id;
   if(ObjectFind(0, boxNm) >= 0) ObjectDelete(0, boxNm);
   if(ObjectFind(0, ceNm)  >= 0) ObjectDelete(0, ceNm);
}
//+------------------------------------------------------------------+
