"""Deflated Sharpe ratio (Bailey & López de Prado, 2014).

Corrects an observed Sharpe for multiple testing (number of strategy-family
trials), non-normal returns (skew/kurtosis) and track length. The expected
maximum Sharpe under N independent zero-skill trials is

    SR0 = sqrt(V[SR_trials]) * ((1-gamma) * z(1 - 1/N) + gamma * z(1 - 1/(N*e)))

and DSR = PSR(SR0) = Phi( (SR - SR0) * sqrt(n-1) /
                          sqrt(1 - skew*SR + (kurt-1)/4 * SR^2) ).

`sr_excess = SR - SR0 < 0` (deflated Sharpe below zero) is a hard REJECT.
Trial counting is per strategy family: count_family_trials() queries
backtest_runs for the family.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

EULER_GAMMA = 0.5772156649015329


@dataclass(frozen=True)
class DeflatedSharpeResult:
    sharpe: float  # observed per-trade SR (non-annualized)
    sr0: float  # expected max SR of N zero-skill trials
    sr_excess: float  # sharpe - sr0; < 0 => REJECT
    dsr: float  # probability the true SR exceeds SR0
    n_trials: int
    n_obs: int

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in
                ("sharpe", "sr0", "sr_excess", "dsr", "n_trials", "n_obs")}


def expected_max_sharpe(n_trials: int, var_trial_sr: float) -> float:
    if n_trials <= 1:
        return 0.0
    e = np.e
    z1 = stats.norm.ppf(1 - 1.0 / n_trials)
    z2 = stats.norm.ppf(1 - 1.0 / (n_trials * e))
    return float(np.sqrt(var_trial_sr) * ((1 - EULER_GAMMA) * z1 + EULER_GAMMA * z2))


def deflated_sharpe(
    r: np.ndarray,
    n_trials: int = 1,
    trial_sr_var: float | None = None,
) -> DeflatedSharpeResult:
    """Compute DSR for a per-trade R stream.

    trial_sr_var: cross-trial variance of Sharpe estimates; defaults to the
    estimator variance of this track's SR (a conservative stand-in when the
    family's trial SRs were not recorded).
    """
    r = np.asarray(r, dtype=np.float64)
    n = len(r)
    if n < 10:
        raise ValueError("need at least 10 observations")
    sd = float(np.std(r, ddof=1))
    sr = float(np.mean(r)) / sd if sd > 0 else 0.0
    skew = float(stats.skew(r))
    kurt = float(stats.kurtosis(r, fisher=False))

    if trial_sr_var is None:
        trial_sr_var = (1 - skew * sr + (kurt - 1) / 4 * sr**2) / (n - 1)
        trial_sr_var = max(trial_sr_var, 1e-12)
    sr0 = expected_max_sharpe(n_trials, trial_sr_var)

    denom = 1 - skew * sr + (kurt - 1) / 4 * sr**2
    denom = max(denom, 1e-12)
    z = (sr - sr0) * np.sqrt(n - 1) / np.sqrt(denom)
    return DeflatedSharpeResult(
        sharpe=sr, sr0=sr0, sr_excess=sr - sr0, dsr=float(stats.norm.cdf(z)),
        n_trials=n_trials, n_obs=n,
    )


def count_family_trials(session, family: str) -> int:
    """Number of recorded backtest runs for a strategy family (>=1)."""
    from sqlalchemy import func, select

    from core.db import BacktestRun, Strategy

    n = session.execute(
        select(func.count(BacktestRun.id))
        .join(Strategy, BacktestRun.strategy_id == Strategy.id)
        .where(Strategy.family == family)
    ).scalar_one()
    return max(int(n), 1)
