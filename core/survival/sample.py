"""Sample trades.csv generator with configurable win rate / reward / MAE.

Usage: python -m core.survival.sample --out trades.csv --n 600 \
           --win-rate 0.5 --reward 2.0 --mae 1.5
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SESSIONS = ((8, "london"), (13, "newyork"), (16, "newyork"))


def generate_sample_trades(
    n: int = 600,
    win_rate: float = 0.5,
    reward_r: float = 2.0,
    mae_r: float = 1.5,
    trades_per_day: int = 3,
    start: str = "2024-01-01",
    seed: int = 42,
    r_jitter: float = 0.15,
    instrument: str = "EURUSD",
) -> pd.DataFrame:
    """Generate a synthetic trade list.

    Winners close near +reward_r; losers near -1R. `mae_r` is the worst-case
    intra-trade adverse excursion in R units: losers float between 1R and
    mae_r (slippage / loose intraday stop) before closing at -1R, winners
    float up to min(1, mae_r)*0.8 before working out.
    """
    rng = np.random.default_rng(seed)
    wins = rng.random(n) < win_rate
    r = np.where(wins, reward_r, -1.0) + rng.normal(0.0, r_jitter, n)
    r = np.where(wins, np.maximum(r, 0.1), np.minimum(r, -0.5))

    mae_win = rng.uniform(0.05, max(min(1.0, mae_r) * 0.8, 0.1), n)
    mae_loss = rng.uniform(1.0, max(mae_r, 1.0 + 1e-9), n)
    mae = np.where(wins, mae_win, np.maximum(mae_loss, -r))

    mfe = np.where(wins, np.abs(r) + rng.uniform(0.0, 0.3, n), rng.uniform(0.0, 0.6, n))

    bdays = pd.bdate_range(start=start, periods=(n + trades_per_day - 1) // trades_per_day, tz="UTC")
    entries, sessions = [], []
    for i in range(n):
        day = bdays[i // trades_per_day]
        hour, sess = SESSIONS[(i % trades_per_day) % len(SESSIONS)]
        entries.append(day + pd.Timedelta(hours=hour, minutes=int(rng.integers(0, 50))))
        sessions.append(sess)
    entry_time = pd.DatetimeIndex(entries)
    hold = pd.to_timedelta(rng.uniform(0.5, 3.0, n), unit="h")

    return pd.DataFrame({
        "entry_time": entry_time,
        "exit_time": entry_time + hold,
        "instrument": instrument,
        "direction": rng.choice(["long", "short"], n),
        "r_multiple": np.round(r, 4),
        "mae_r": np.round(mae, 4),
        "mfe_r": np.round(mfe, 4),
        "session": sessions,
    })


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Generate a sample trades.csv")
    p.add_argument("--out", type=Path, default=Path("trades.csv"))
    p.add_argument("--n", type=int, default=600)
    p.add_argument("--win-rate", type=float, default=0.5)
    p.add_argument("--reward", type=float, default=2.0)
    p.add_argument("--mae", type=float, default=1.5)
    p.add_argument("--trades-per-day", type=int, default=3)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--start", type=str, default="2024-01-01")
    args = p.parse_args(argv)

    df = generate_sample_trades(
        n=args.n, win_rate=args.win_rate, reward_r=args.reward, mae_r=args.mae,
        trades_per_day=args.trades_per_day, start=args.start, seed=args.seed,
    )
    df.to_csv(args.out, index=False)
    exp = df["r_multiple"].mean()
    print(f"Wrote {len(df)} trades to {args.out} (expectancy {exp:+.3f}R, "
          f"win rate {(df['r_multiple'] > 0).mean():.1%})")


if __name__ == "__main__":
    main()
