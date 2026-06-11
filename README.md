# Serpent Lab v2

Quantitative research and portfolio management system for validating,
deploying and monitoring trading EAs targeting an FTMO funded account
(2-Step: Phase 1 = 10%, Phase 2 = 5%, 5% max daily loss equity-based from the
midnight-CET snapshot with floating PnL counting, 10% static max total loss,
min 4 trading days, no time limit, 80% funded split).

## Layout

```
api/            FastAPI routers + /ws/live websocket
core/
  survival/     Module 1: prop-firm survival Monte Carlo (numba)
  overfit/      Module 2: overfitting battery + robustness score
  regime/       Module 3: rule + GaussianHMM regime engine
  dna/          Module 4: strategy DNA analyzer
  portfolio/    Module 5: portfolio construction (caps, frontier, survival-verified)
  decay/        Module 6: edge decay monitor + state machine
bridge/         MT5 -> zstd parquet ingest, JSON signal IO (see SIGNAL_CONTRACT.md)
data/           parquet store + sqlite db (gitignored)
scripts/        demo_pipeline.py — full end-to-end run on sample data
tests/          pytest suite (83 tests, deterministic seeds)
```

## Setup

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e .[dev]
python -m core.init_db                      # create data/serpent.db
```

## Quick start

```bash
# generate sample trades and run the FTMO survival risk sweep
python -m core.survival.sample --out trades.csv --n 600 --win-rate 0.5 --reward 2 --mae 1.5
python -m core.survival.cli --trades trades.csv --firm ftmo_100k_2step --sweep 0.25 2.0 0.25

# full pipeline demo (survival -> overfit -> regime -> DNA -> portfolio -> decay -> signals)
python scripts/demo_pipeline.py

# API with OpenAPI docs at /docs
uvicorn api.main:app --reload

pytest
```

## Module notes

1. **Survival** — block-bootstrap of whole trading days (midnight **CET/CEST**
   boundary via Europe/Prague), MAE-based intra-trade equity troughs so daily
   breaches are caught mid-trade, min-trading-days gate, funded-stage EV with
   configurable challenge fee. Firm rules are YAML
   (`core/survival/firms/ftmo_100k_2step.yaml`); validated against analytic
   gambler's-ruin cases in tests.
2. **Overfit** — walk-forward efficiency, CPCV (10 groups, 45 combos, purge +
   embargo, p5 OOS Sharpe), MC reshuffle/deletion/slippage, parameter plateau,
   deflated Sharpe with family trial counts. Composite 0–100
   (25/20/15/15/10/10/5); <100 trades caps at 40, deflated Sharpe < 0 rejects.
3. **Regime** — ADX, regression R²/slope, ATR percentile, vol-of-vol, Hurst,
   Kaufman ER → CRISIS / HIGH_VOL_TREND / LOW_VOL_TREND / MEAN_REVERT /
   SIDEWAYS_QUIET / SIDEWAYS_CHOP with bull/bear overlay; GaussianHMM (10
   restarts) on top; regime × strategy matrix with enable/disable recs.
4. **DNA** — convexity, vol exposure, full + crisis correlations, cost
   sensitivity 1×/1.5×/2×, session dependency, failure conditions.
5. **Portfolio** — inverse-vol / ERC / constrained max-Sharpe (30% per
   strategy, 50% per edge source, 40% per instrument) on the **worse of
   full-sample vs crisis correlation**; 10k random-weight frontier; objective
   E[monthly] / max(p95 DD, 4%) s.t. P(10% breach in 6 mo) < 5% and P(daily
   breach) < 2%, every candidate verified through the survival simulator.
6. **Decay** — CUSUM (3σ√n), DD envelope vs own MC distribution (p95 REDUCED
   → halve risk, p99 SUSPENDED), KS shift on last 30 trades, regime-mismatch
   suppression; HEALTHY→WATCH→REDUCED→SUSPENDED→RETIRED, transitions logged
   to `alerts` with evidence.
7. **Bridge + API** — MT5 ingest (Windows-only package import-guarded) to
   zstd parquet; atomic `signals.json` consumed by the MQL5 EA
   (`bridge/SIGNAL_CONTRACT.md`); FastAPI endpoints `POST /prop-sim`,
   `GET /prop-sim/{id}`, `POST /backtests`, `GET /backtests/{id}/robustness`,
   `GET /strategies/{id}/dna`, `GET /strategies/{id}/regime-matrix`,
   `POST /portfolios/optimize`, `GET /ops/state`, `GET /alerts`, `WS /ws/live`.
