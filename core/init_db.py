"""Initialize the Serpent Lab SQLite database.

Usage: python -m core.init_db [--db data/serpent.db]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from core.config import get_settings
from core.db import get_engine, init_db


def main(argv: list[str] | None = None) -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Initialize Serpent Lab database")
    parser.add_argument("--db", type=Path, default=settings.db_path)
    args = parser.parse_args(argv)

    engine = get_engine(args.db)
    init_db(engine)
    settings.parquet_dir.mkdir(parents=True, exist_ok=True)
    settings.signals_dir.mkdir(parents=True, exist_ok=True)
    print(f"Database initialized at {args.db}")


if __name__ == "__main__":
    main()
