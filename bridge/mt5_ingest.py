"""MetaTrader5 -> zstd Parquet ingest.

The `MetaTrader5` package only exists on Windows; everything that touches it
is guarded so the parquet store, tests and API run anywhere. On the trading
machine, run e.g.:

    python -m bridge.mt5_ingest --symbol EURUSD --timeframe H1 --days 365
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from core.config import get_settings

try:  # Windows-only package
    import MetaTrader5 as mt5  # type: ignore
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False

PARQUET_COMPRESSION = "zstd"
TIMEFRAME_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}


def bars_path(parquet_dir: Path, symbol: str, timeframe: str) -> Path:
    return Path(parquet_dir) / "bars" / f"{symbol}_{timeframe}.parquet"


def write_bars_parquet(df: pd.DataFrame, path: Path) -> Path:
    """Write OHLC bars (UTC DatetimeIndex named 'time') as zstd parquet,
    merging with and de-duplicating against any existing file."""
    if df.index.name != "time":
        df = df.rename_axis("time")
    if df.index.tz is None:
        df = df.tz_localize("UTC")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        old = pd.read_parquet(path)
        df = pd.concat([old, df])
        df = df[~df.index.duplicated(keep="last")].sort_index()
    df.to_parquet(path, compression=PARQUET_COMPRESSION)
    return path


def read_bars_parquet(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def _require_mt5() -> None:
    if not MT5_AVAILABLE:
        raise RuntimeError(
            "MetaTrader5 package is not available on this platform (Windows only). "
            "Run the ingest on the trading machine; the parquet store is portable."
        )


def fetch_bars_mt5(symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
    """Pull OHLCV bars from a running MT5 terminal."""
    _require_mt5()
    tf = getattr(mt5, f"TIMEFRAME_{timeframe}")
    if not mt5.initialize():
        raise RuntimeError(f"mt5.initialize failed: {mt5.last_error()}")
    try:
        rates = mt5.copy_rates_range(symbol, tf, start, end)
    finally:
        mt5.shutdown()
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"no bars returned for {symbol} {timeframe}")
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("time").rename(columns={"tick_volume": "volume"})
    return df[["open", "high", "low", "close", "volume", "spread"]]


def ingest(symbol: str, timeframe: str, days: int, parquet_dir: Path | None = None) -> Path:
    """Fetch from MT5 and persist to the parquet store."""
    settings = get_settings()
    out_dir = parquet_dir or settings.parquet_dir
    end = datetime.now(timezone.utc)
    df = fetch_bars_mt5(symbol, timeframe, end - timedelta(days=days), end)
    return write_bars_parquet(df, bars_path(out_dir, symbol, timeframe))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Ingest MT5 bars to zstd parquet")
    p.add_argument("--symbol", required=True)
    p.add_argument("--timeframe", default="H1", choices=sorted(TIMEFRAME_MINUTES))
    p.add_argument("--days", type=int, default=365)
    p.add_argument("--parquet-dir", type=Path, default=None)
    args = p.parse_args(argv)
    path = ingest(args.symbol, args.timeframe, args.days, args.parquet_dir)
    print(f"Ingested {args.symbol} {args.timeframe} -> {path}")


if __name__ == "__main__":
    main()
