"""Numba-accelerated prop-firm survival Monte Carlo.

Model
-----
- Block-bootstrap resampling of *trading days* (blocks of consecutive source
  days) so intra-day trade sequencing and day-to-day autocorrelation are
  preserved.
- Day-by-day simulation with the daily-loss anchor reset at midnight in the
  firm timezone: anchor = equity at the start of the simulated day.
- Intra-trade floating loss: each trade first dips to -MAE x risk before
  settling at its final R, so equity-based daily/total breaches are caught
  MID-TRADE, not just at trade close.
- Risk is a fixed fraction of the initial balance per 1R (standard prop-firm
  position sizing). Equity is normalized to initial balance = 1.0.
- A phase passes when balance reaches the target; if the minimum trading-day
  count is not yet met, the trader idles flat for the remaining days (days to
  pass is floored at min_trading_days).
- After all phases pass, an optional funded stage is simulated for EV: every
  `payout_every_days` trading days, profit_split x profit is withdrawn and the
  balance resets to initial; a breach ends the funded stage (payouts kept).

Outcome codes: 0=PASS, 1=BUST_DAILY, 2=BUST_TOTAL, 3=TIMEOUT.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numba import njit, prange

from core.survival.firm import FirmConfig
from core.survival.trades_io import DayGroupedTrades

PASS, BUST_DAILY, BUST_TOTAL, TIMEOUT = 0, 1, 2, 3
_EPS = 1e-12
_MASK = np.uint64(0xFFFFFFFFFFFFFFFF)


@njit(cache=True, inline="always")
def _rng_next(state: np.uint64) -> tuple[np.uint64, np.uint64]:
    """xorshift64* — deterministic, thread-safe per-path RNG."""
    s = state
    s ^= s >> np.uint64(12)
    s ^= (s << np.uint64(25)) & _MASK
    s ^= s >> np.uint64(27)
    out = (s * np.uint64(0x2545F4914F6CDD1D)) & _MASK
    return s, out


@njit(cache=True, inline="always")
def _randint(state: np.uint64, n: int) -> tuple[np.uint64, int]:
    state, x = _rng_next(state)
    # explicit signed cast: numba unifies uint64/int64 to float64 otherwise
    return state, np.int64(x % np.uint64(n))


@njit(cache=True)
def _run_stage(
    state: np.uint64,
    day_ptr: np.ndarray,
    r: np.ndarray,
    mae: np.ndarray,
    block_size: int,
    risk: float,
    daily_limit: float,  # <=0 disables the daily check
    total_floor: float,  # absolute equity floor (1 - max_total_loss)
    target: float,  # absolute balance target (>1); <=0 disables (funded stage)
    min_days: int,
    max_days: int,
    payout_every: int,  # 0 = no payouts (challenge phases)
    split: float,
) -> tuple[np.uint64, int, int, float, float]:
    """Simulate one stage. Returns (rng_state, status, trading_days, equity, payouts).

    status: 0 target hit / horizon survived, 1 daily bust, 2 total bust, 3 timeout.
    """
    equity = 1.0
    days = 0
    payouts = 0.0
    block_left = 0
    src_day = 0
    n_src = len(day_ptr) - 1

    while days < max_days:
        if block_left == 0:
            state, src_day = _randint(state, n_src)
            block_left = block_size
        else:
            src_day = (src_day + 1) % n_src
        block_left -= 1

        anchor = equity  # midnight-CET balance/equity snapshot
        cum = equity
        hit = False
        for k in range(day_ptr[src_day], day_ptr[src_day + 1]):
            low = cum - mae[k] * risk  # floating trough, mid-trade
            if daily_limit > 0.0 and low <= anchor - daily_limit + _EPS:
                return state, BUST_DAILY, days + 1, low, payouts
            if low <= total_floor + _EPS:
                return state, BUST_TOTAL, days + 1, low, payouts
            cum += r[k] * risk  # trade closes
            if target > 0.0 and cum >= target - _EPS:
                hit = True
                break
        equity = cum
        days += 1

        if hit:
            if days < min_days:
                days = min_days  # idle flat to satisfy the min trading-days gate
            return state, PASS, days, equity, payouts

        if payout_every > 0 and days % payout_every == 0 and equity > 1.0:
            payouts += split * (equity - 1.0)
            equity = 1.0  # withdrawal resets balance to initial

    if target <= 0.0:  # funded stage: surviving the horizon is success
        return state, PASS, days, equity, payouts
    return state, TIMEOUT, days, equity, payouts


@njit(cache=True)
def _simulate_path(
    seed: np.uint64,
    day_ptr: np.ndarray,
    r: np.ndarray,
    mae: np.ndarray,
    block_size: int,
    risk: float,
    daily_limit: float,
    total_floor: float,
    targets: np.ndarray,
    min_days: np.ndarray,
    max_days_phase: int,
    funded_days: int,
    payout_every: int,
    split: float,
) -> tuple[int, int, float]:
    """One full attempt: all challenge phases, then the funded stage for EV."""
    # splitmix-style seed scramble so consecutive path ids decorrelate
    state = (seed ^ np.uint64(0x9E3779B97F4A7C15)) | np.uint64(1)
    state, _ = _rng_next(state)

    total_days = 0
    for ph in range(len(targets)):
        state, status, days, _, _ = _run_stage(
            state, day_ptr, r, mae, block_size, risk, daily_limit, total_floor,
            targets[ph], min_days[ph], max_days_phase, 0, 0.0,
        )
        total_days += days
        if status != PASS:
            return status, total_days, 0.0

    payouts = 0.0
    if funded_days > 0:
        state, _, _, _, payouts = _run_stage(
            state, day_ptr, r, mae, block_size, risk, daily_limit, total_floor,
            -1.0, 0, funded_days, payout_every, split,
        )
    return PASS, total_days, payouts


@njit(cache=True, parallel=True)
def _simulate_many(
    n_paths: int,
    base_seed: int,
    day_ptr: np.ndarray,
    r: np.ndarray,
    mae: np.ndarray,
    block_size: int,
    risk: float,
    daily_limit: float,
    total_floor: float,
    targets: np.ndarray,
    min_days: np.ndarray,
    max_days_phase: int,
    funded_days: int,
    payout_every: int,
    split: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    outcomes = np.empty(n_paths, dtype=np.int64)
    days = np.empty(n_paths, dtype=np.int64)
    payouts = np.empty(n_paths, dtype=np.float64)
    for i in prange(n_paths):
        o, d, p = _simulate_path(
            np.uint64(base_seed + i), day_ptr, r, mae, block_size, risk,
            daily_limit, total_floor, targets, min_days, max_days_phase,
            funded_days, payout_every, split,
        )
        outcomes[i] = o
        days[i] = d
        payouts[i] = p
    return outcomes, days, payouts


@dataclass(frozen=True)
class SimResult:
    """Aggregated Monte Carlo result for one risk level."""

    risk_pct: float
    n_paths: int
    p_pass: float
    p_bust_daily: float
    p_bust_total: float
    p_timeout: float
    days_to_pass_median: float
    days_to_pass_p10: float
    days_to_pass_p90: float
    ev_per_attempt: float  # account currency, net of challenge fee
    expected_payout: float  # account currency, funded-stage payouts only
    raw: dict = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        d = {k: getattr(self, k) for k in (
            "risk_pct", "n_paths", "p_pass", "p_bust_daily", "p_bust_total",
            "p_timeout", "days_to_pass_median", "days_to_pass_p10",
            "days_to_pass_p90", "ev_per_attempt", "expected_payout",
        )}
        return d


def run_prop_sim(
    days: DayGroupedTrades,
    firm: FirmConfig,
    risk_pct: float,
    n_paths: int = 20_000,
    seed: int = 42,
    block_size: int = 5,
    simulate_funded: bool = True,
) -> SimResult:
    """Run the survival Monte Carlo for one per-trade risk level (in % of initial balance)."""
    if days.n_days < 1:
        raise ValueError("need at least one source trading day")
    if days.n_days < block_size:
        block_size = days.n_days

    targets = np.array([1.0 + ph.profit_target_pct / 100.0 for ph in firm.phases], dtype=np.float64)
    min_days = np.array([ph.min_trading_days for ph in firm.phases], dtype=np.int64)
    daily_limit = (firm.daily_loss_pct or 0.0) / 100.0
    total_floor = 1.0 - firm.max_total_loss_pct / 100.0
    phase_caps = [ph.max_days if ph.max_days is not None else firm.sim_max_days_per_phase for ph in firm.phases]
    max_days_phase = int(max(phase_caps))
    funded_days = firm.funded.horizon_days if simulate_funded else 0

    outcomes, days_arr, payouts = _simulate_many(
        n_paths, seed, days.day_ptr, days.r, days.mae, block_size,
        risk_pct / 100.0, daily_limit, total_floor, targets, min_days,
        max_days_phase, funded_days, firm.funded.payout_every_days,
        firm.funded.profit_split,
    )

    passed = outcomes == PASS
    p_pass = float(passed.mean())
    pass_days = days_arr[passed]
    q = (np.percentile(pass_days, [50, 10, 90]) if pass_days.size else np.full(3, np.nan))

    expected_payout = float(payouts.mean()) * firm.account_size
    refund = 0.0
    if firm.funded.fee_refund_on_first_payout and simulate_funded:
        refund = firm.challenge_fee * float((payouts > 0).mean())
    ev = expected_payout + refund - firm.challenge_fee

    return SimResult(
        risk_pct=risk_pct,
        n_paths=n_paths,
        p_pass=p_pass,
        p_bust_daily=float((outcomes == BUST_DAILY).mean()),
        p_bust_total=float((outcomes == BUST_TOTAL).mean()),
        p_timeout=float((outcomes == TIMEOUT).mean()),
        days_to_pass_median=float(q[0]),
        days_to_pass_p10=float(q[1]),
        days_to_pass_p90=float(q[2]),
        ev_per_attempt=ev,
        expected_payout=expected_payout,
        raw={"outcomes": outcomes, "days": days_arr, "payouts": payouts},
    )
