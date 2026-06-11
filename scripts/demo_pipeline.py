"""End-to-end Serpent Lab v2 pipeline demo on generated sample data.

Three synthetic strategies (the headline one: 50% win rate, 2R winners,
1.5R max adverse excursion), run through:
  1. survival risk sweep (FTMO 100k 2-step)
  2. overfitting battery -> robustness score
  3. regime engine (rules + HMM) -> regime x strategy matrix
  4. strategy DNA
  5. 3-strategy portfolio: frontier + survival-verified optimization
  6. decay monitor dry-run + signal file emission

Usage: python scripts/demo_pipeline.py [--paths 20000]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.dna.analyzer import analyze_strategy, daily_r_stream
from core.overfit.score import robustness_battery
from core.portfolio.objective import optimize_portfolio
from core.portfolio.weights import PortfolioCaps, StrategyMeta
from core.regime.features import compute_features
from core.regime.hmm import fit_hmm
from core.regime.matrix import pnl_share_by_regime, recommendations, regime_strategy_matrix
from core.regime.rules import classify_rules
from core.regime.sample_data import generate_sample_ohlc
from core.survival.firm import load_firm
from core.survival.sample import generate_sample_trades
from core.survival.sweep import format_sweep_table, run_risk_sweep, sweep_risks
from core.survival.trades_io import group_trades_by_day


def hr(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--paths", type=int, default=20_000)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    firm = load_firm("ftmo_100k_2step")

    # ---- sample data: 3 strategies ------------------------------------
    strategies = {
        "trend_eurusd": dict(n=600, win_rate=0.50, reward_r=2.0, mae_r=1.5, seed=11,
                             instrument="EURUSD", edge="trend"),
        "meanrev_gbpusd": dict(n=600, win_rate=0.58, reward_r=1.4, mae_r=1.3, seed=22,
                               instrument="GBPUSD", edge="mean_revert"),
        "breakout_xauusd": dict(n=600, win_rate=0.44, reward_r=2.4, mae_r=1.5, seed=33,
                                instrument="XAUUSD", edge="breakout"),
    }
    trades_by_strategy, meta = {}, {}
    for name, cfg in strategies.items():
        trades_by_strategy[name] = generate_sample_trades(
            n=cfg["n"], win_rate=cfg["win_rate"], reward_r=cfg["reward_r"],
            mae_r=cfg["mae_r"], seed=cfg["seed"], instrument=cfg["instrument"])
        meta[name] = StrategyMeta(edge_source=cfg["edge"], instrument=cfg["instrument"])

    headline = "trend_eurusd"
    df = trades_by_strategy[headline]

    # ---- 1. survival risk sweep ----------------------------------------
    hr(f"1. SURVIVAL — {headline} (50% WR, 2R, 1.5R MAE), {args.paths} MC paths")
    days = group_trades_by_day(df, tz=firm.timezone)
    results = run_risk_sweep(days, firm, sweep_risks(0.25, 2.0, 0.25),
                             n_paths=args.paths, seed=args.seed)
    print(format_sweep_table(results, firm))

    # ---- 3. regime engine (needed for robustness regime component) -----
    hr("3. REGIME — rule layer + HMM on synthetic EURUSD daily bars")
    bars = generate_sample_ohlc(start="2023-10-02", seed=7)
    feats = compute_features(bars)
    labels = classify_rules(feats)
    hmm = fit_hmm(feats, labels["regime"], n_states=4, n_restarts=10, seed=args.seed)
    print(f"HMM best log-likelihood over 10 restarts: {hmm.log_likelihood:,.1f}")
    print("state -> rule label:", hmm.state_names)
    print("transition matrix:")
    print(np.array_str(hmm.transition_matrix, precision=3, suppress_small=True))

    all_trades = pd.concat(
        [t.assign(strategy=n) for n, t in trades_by_strategy.items()], ignore_index=True)
    matrix = regime_strategy_matrix(all_trades, labels["regime"])
    with pd.option_context("display.width", 120):
        print("\nregime x strategy matrix:")
        print(matrix.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    recs = [r for r in recommendations(matrix) if r.action != "neutral"]
    for r in recs[:8]:
        print(f"  [{r.action.upper():7s}] {r.strategy} in {r.regime}: {r.reason}")

    # ---- 2. robustness -------------------------------------------------
    hr(f"2. OVERFIT — robustness battery for {headline}")
    grid = pd.DataFrame([{"lookback": lb, "atr_mult": am,
                          "metric": 0.45 - 0.002 * abs(lb - 50) - 0.05 * abs(am - 2.0)}
                         for lb in range(30, 75, 5) for am in (1.5, 1.75, 2.0, 2.25, 2.5)])
    report = robustness_battery(df, param_results=grid, n_trials=3,
                                pnl_share_by_regime=pnl_share_by_regime(matrix, headline),
                                seed=args.seed)
    print(f"ROBUSTNESS SCORE: {report.score:.1f}/100  ->  {report.verdict}")
    for k, v in report.components.items():
        print(f"  {k:12s} {v:6.2f}")
    ds = report.details["deflated_sharpe"]
    print(f"  deflated Sharpe: SR {ds['sharpe']:.3f}, SR0 {ds['sr0']:.3f}, "
          f"excess {ds['sr_excess']:+.3f}, DSR {ds['dsr']:.3f}")
    if report.gates:
        print("  gates:", "; ".join(report.gates))

    # ---- 4. DNA ---------------------------------------------------------
    hr(f"4. DNA — {headline}")
    streams = {n: daily_r_stream(t) for n, t in trades_by_strategy.items()}
    crisis_days = pd.DatetimeIndex(labels.index[labels["regime"] == "CRISIS"])
    dna = analyze_strategy(headline, df, streams, regime_matrix=matrix,
                           crisis_days=crisis_days, edge_source="trend")
    print(f"frequency: {dna.trades_per_week:.1f} trades/wk | expectancy {dna.expectancy_r:+.3f}R")
    print(f"convexity: skew {dna.convexity['skew']:+.2f}, tail ratio {dna.convexity['tail_ratio']:.2f}")
    print(f"correlations (full):   {dna.correlations_full}")
    print(f"correlations (crisis): {dna.correlations_crisis}")
    print(f"cost sensitivity: {dna.cost_sensitivity}")
    print(f"best regimes: {dna.best_regimes} | worst: {dna.worst_regimes}")
    print("failure conditions:", dna.failure_conditions or "none detected")

    # ---- 5. portfolio ---------------------------------------------------
    hr("5. PORTFOLIO — 3-strategy frontier + survival-verified optimization")
    streams_df = pd.DataFrame(streams)
    opt = optimize_portfolio(streams_df, trades_by_strategy, firm, meta=meta,
                             crisis_days=crisis_days,
                             caps=PortfolioCaps(per_strategy=0.40),
                             risk_grid=(0.5, 0.75, 1.0, 1.25, 1.5),
                             n_frontier=10_000, n_paths=5_000, seed=args.seed)
    pareto = opt.frontier[opt.frontier["pareto"]].sort_values("max_dd")
    print(f"frontier: {len(opt.frontier)} random portfolios, {len(pareto)} on the Pareto front")
    cols = list(streams_df.columns)
    print(pareto[cols + ["cagr", "max_dd"]].head(12)
          .to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print("\ncandidates (best risk level each):")
    by_name: dict[str, object] = {}
    for c in opt.candidates:
        if c.feasible and (c.name not in by_name or c.objective > by_name[c.name].objective):
            by_name[c.name] = c
    for c in by_name.values():
        w = ", ".join(f"{k} {v:.0%}" for k, v in c.weights.items())
        print(f"  {c.name:12s} risk {c.risk_pct:.2f}% | E[monthly] {c.monthly_return_pct:5.2f}% | "
              f"p95 DD {c.dd_p95_pct:4.2f}% | P(10% 6mo) {c.p_breach_total_6mo:.2%} | "
              f"P(daily) {c.p_breach_daily:.2%} | obj {c.objective:.3f} | {w}")
    b = opt.best
    print(f"\nBEST: {b.name} @ {b.risk_pct:.2f}% risk -> objective {b.objective:.3f} "
          f"(constraints: P(10%/6mo)={b.p_breach_total_6mo:.2%}<5%, "
          f"P(daily)={b.p_breach_daily:.2%}<2%)")

    # ---- 6. decay + signals ---------------------------------------------
    hr("6. DECAY + SIGNALS — initial states and signal file")
    from core.decay.state_machine import evaluate_decay
    from bridge.signals import SignalFile, StrategySignal, write_signals
    from datetime import datetime, timezone

    sig = SignalFile(generated_at=datetime.now(timezone.utc), account="demo")
    for i, (name, t) in enumerate(trades_by_strategy.items()):
        ev = evaluate_decay(name, "HEALTHY", t.tail(50), t["r_multiple"].to_numpy(),
                            seed=args.seed)
        risk = b.weights.get(name, 0.0) * b.risk_pct * ev.risk_multiplier
        sig.strategies[name] = StrategySignal(magic=770001 + i, enabled=risk > 0,
                                              risk_pct=round(risk, 3), state=ev.new_state)
        print(f"  {name:16s} {ev.previous_state} -> {ev.new_state} | signal risk {risk:.3f}%")
    out = write_signals(sig, Path("data/signals"))
    print(f"signal file written: {out}")


if __name__ == "__main__":
    main()
