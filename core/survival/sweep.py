"""Risk sweep across per-trade risk levels."""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.survival.firm import FirmConfig
from core.survival.mc import SimResult, run_prop_sim
from core.survival.trades_io import DayGroupedTrades


def sweep_risks(start: float, stop: float, step: float) -> list[float]:
    n = int(round((stop - start) / step)) + 1
    return [round(start + i * step, 6) for i in range(n)]


def run_risk_sweep(
    days: DayGroupedTrades,
    firm: FirmConfig,
    risks: list[float],
    n_paths: int = 20_000,
    seed: int = 42,
    block_size: int = 5,
    simulate_funded: bool = True,
) -> list[SimResult]:
    return [
        run_prop_sim(days, firm, risk, n_paths=n_paths, seed=seed + i,
                     block_size=block_size, simulate_funded=simulate_funded)
        for i, risk in enumerate(risks)
    ]


def sweep_to_frame(results: list[SimResult]) -> pd.DataFrame:
    return pd.DataFrame([r.to_dict() for r in results])


def format_sweep_table(results: list[SimResult], firm: FirmConfig) -> str:
    """Human-readable risk-sweep table."""
    header = (
        f"{'risk%':>6} {'P(pass)':>8} {'P(daily)':>9} {'P(total)':>9} {'P(t/o)':>7} "
        f"{'med days':>9} {'p10':>6} {'p90':>6} {'E[payout]':>11} {'EV/attempt':>11}"
    )
    lines = [f"Firm: {firm.name}  (fee {firm.challenge_fee:.0f} {firm.currency}, "
             f"funded horizon {firm.funded.horizon_days}d, split {firm.funded.profit_split:.0%})",
             header, "-" * len(header)]
    for r in results:
        med = "-" if np.isnan(r.days_to_pass_median) else f"{r.days_to_pass_median:9.0f}"
        p10 = "-" if np.isnan(r.days_to_pass_p10) else f"{r.days_to_pass_p10:6.0f}"
        p90 = "-" if np.isnan(r.days_to_pass_p90) else f"{r.days_to_pass_p90:6.0f}"
        lines.append(
            f"{r.risk_pct:6.2f} {r.p_pass:8.1%} {r.p_bust_daily:9.1%} {r.p_bust_total:9.1%} "
            f"{r.p_timeout:7.1%} {med:>9} {p10:>6} {p90:>6} "
            f"{r.expected_payout:11.0f} {r.ev_per_attempt:11.0f}"
        )
    return "\n".join(lines)
