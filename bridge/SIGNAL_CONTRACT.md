# Serpent Lab ⇄ MQL5 EA signal contract

Serpent Lab and the EA communicate exclusively through JSON files in the MT5
`MQL5/Files/serpent/` directory (configure `SERPENT_SIGNALS_DIR` to point at
it). No sockets, no DLLs — survives broker VPS restrictions.

## `signals.json` (written by Serpent Lab, read by the EA)

Written **atomically** (temp file + rename). The EA should re-read it on a
timer (recommended: every 5–15 s) and whenever `OnTradeTransaction` fires.

```json
{
  "version": 2,
  "generated_at": "2026-06-11T14:05:00Z",
  "account": "ftmo-100k-001",
  "kill_switch": false,
  "strategies": {
    "trend_eurusd_h1": {
      "magic": 770001,
      "enabled": true,
      "risk_pct": 1.0,
      "state": "HEALTHY",
      "comment": "all detectors clean"
    },
    "mr_gbpusd_m15": {
      "magic": 770002,
      "enabled": true,
      "risk_pct": 0.25,
      "state": "REDUCED",
      "comment": "dd_envelope live 9.2R >= p95 8.8R"
    },
    "breakout_xauusd_h1": {
      "magic": 770003,
      "enabled": false,
      "risk_pct": 0.0,
      "state": "SUSPENDED",
      "comment": "cusum_drift z=3.40 >= 3.0"
    }
  }
}
```

### Field semantics

| Field | Type | Meaning |
|---|---|---|
| `version` | int | Contract version. EA must refuse files with a version it doesn't know. |
| `generated_at` | ISO-8601 UTC | Staleness check: if older than `MaxSignalAgeMinutes` (EA input, default 60), the EA must stop **opening** new positions (keep managing open ones) and alert. |
| `account` | string | Informational routing tag. |
| `kill_switch` | bool | `true` → EA closes all positions at market, disables all strategies, and stops trading until a new file with `false` arrives. |
| `strategies.*` | object | Keyed by strategy name; the EA matches on `magic`. |
| `magic` | int | EA magic number. Unknown magics in the file are ignored by the EA; EA strategies *absent* from the file must trade with `enabled=false`. |
| `enabled` | bool | `false` → no **new** entries. Open positions are managed to their normal exits (the risk engine handles equity floors separately). |
| `risk_pct` | float | Per-trade risk as % of **initial account balance** (fixed-fractional, FTMO-style sizing): `lots = risk_pct/100 * initial_balance / (stop_distance_points * point_value)`. |
| `state` | string | `HEALTHY/WATCH/REDUCED/SUSPENDED/RETIRED` — informational, for the EA log/comment. |
| `comment` | string | Human-readable reason, for logs only. |

### EA-side rules

1. Parse failures or unknown `version` → treat as `kill_switch` for new
   entries and log; never crash, never guess.
2. Apply `risk_pct` only to entries placed *after* the file was read.
3. A strategy missing from `strategies` → `enabled=false, risk_pct=0`.

## `signals_ack.json` (written by the EA, read by Serpent Lab)

The EA writes this after applying each signal file so the ops dashboard can
verify the loop is closed:

```json
{
  "applied_at": "2026-06-11T14:05:09Z",
  "signals_generated_at": "2026-06-11T14:05:00Z",
  "terminal": {"login": 1520012345, "server": "FTMO-Server3"},
  "balance": 100412.55,
  "equity": 100388.10,
  "applied": {"trend_eurusd_h1": "enabled@1.00%", "mr_gbpusd_m15": "enabled@0.25%"}
}
```

`applied_at` minus `signals_generated_at` is the end-to-end latency;
Serpent Lab raises a bridge alert when it exceeds the configured threshold or
when the ack goes stale.
