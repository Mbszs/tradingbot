"""Survival Monte Carlo CLI.

Usage:
    python -m core.survival.cli --trades trades.csv --firm ftmo_100k_2step \
        --sweep 0.25 2.0 0.25 [--paths 20000 --seed 42 --block 5] [--save-db]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.config import get_settings
from core.survival.firm import load_firm
from core.survival.sweep import format_sweep_table, run_risk_sweep, sweep_risks, sweep_to_frame
from core.survival.trades_io import group_trades_by_day, load_trades_csv


def main(argv: list[str] | None = None) -> None:
    settings = get_settings()
    p = argparse.ArgumentParser(description="Prop-firm survival Monte Carlo risk sweep")
    p.add_argument("--trades", type=Path, required=True, help="trades CSV (r_multiple, mae_r, entry_time)")
    p.add_argument("--firm", type=str, default="ftmo_100k_2step")
    p.add_argument("--sweep", type=float, nargs=3, default=(0.25, 2.0, 0.25),
                   metavar=("START", "STOP", "STEP"), help="risk %% sweep bounds")
    p.add_argument("--risk", type=float, default=None, help="single risk %% (overrides --sweep)")
    p.add_argument("--paths", type=int, default=settings.mc_paths)
    p.add_argument("--seed", type=int, default=settings.mc_seed)
    p.add_argument("--block", type=int, default=settings.mc_block_size, help="bootstrap block size in days")
    p.add_argument("--fee", type=float, default=None, help="override challenge fee")
    p.add_argument("--no-funded", action="store_true", help="skip funded-stage EV simulation")
    p.add_argument("--json-out", type=Path, default=None)
    p.add_argument("--save-db", action="store_true", help="persist results to prop_sims")
    p.add_argument("--db", type=Path, default=settings.db_path)
    args = p.parse_args(argv)

    firm = load_firm(args.firm)
    if args.fee is not None:
        firm = firm.model_copy(update={"challenge_fee": args.fee})

    df = load_trades_csv(args.trades)
    days = group_trades_by_day(df, tz=firm.timezone)
    print(f"Loaded {days.n_trades} trades over {days.n_days} trading days "
          f"(expectancy {df['r_multiple'].mean():+.3f}R)")

    risks = [args.risk] if args.risk is not None else sweep_risks(*args.sweep)
    results = run_risk_sweep(days, firm, risks, n_paths=args.paths, seed=args.seed,
                             block_size=args.block, simulate_funded=not args.no_funded)
    print(format_sweep_table(results, firm))

    payload = sweep_to_frame(results).to_dict(orient="records")
    if args.json_out:
        args.json_out.write_text(json.dumps(payload, indent=2))
        print(f"JSON written to {args.json_out}")
    if args.save_db:
        from core.db import PropSim, get_engine, get_session_factory, init_db

        engine = get_engine(args.db)
        init_db(engine)
        with get_session_factory(engine)() as session:
            sim = PropSim(firm=firm.name, n_paths=args.paths, seed=args.seed,
                          params={"risks": risks, "block": args.block, "trades": str(args.trades)},
                          results=payload)
            session.add(sim)
            session.commit()
            print(f"Saved prop_sim id={sim.id} to {args.db}")


if __name__ == "__main__":
    main()
