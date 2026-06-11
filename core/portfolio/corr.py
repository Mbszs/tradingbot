"""Correlation/covariance assembly for portfolio construction.

Uses the *worse* (higher) of full-sample vs crisis-regime correlation per
pair — diversification that evaporates in a crisis is not diversification —
then projects back to the nearest positive-semidefinite matrix.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def worse_of_correlations(full: pd.DataFrame, crisis: pd.DataFrame | None) -> pd.DataFrame:
    """Elementwise max of the two correlation matrices (NaN crisis cells fall
    back to full-sample), unit diagonal, PSD-repaired."""
    if crisis is None:
        worse = full.copy()
    else:
        crisis = crisis.reindex(index=full.index, columns=full.columns)
        worse = pd.DataFrame(np.fmax(full.to_numpy(), crisis.to_numpy()),
                             index=full.index, columns=full.columns)
    arr = worse.to_numpy(dtype=np.float64)
    arr = np.clip((arr + arr.T) / 2, -1.0, 1.0)
    np.fill_diagonal(arr, 1.0)
    return pd.DataFrame(nearest_psd(arr), index=full.index, columns=full.columns)


def nearest_psd(corr: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    """Eigenvalue clipping + re-normalization to unit diagonal."""
    vals, vecs = np.linalg.eigh(corr)
    if vals.min() >= eps:
        return corr
    vals = np.clip(vals, eps, None)
    fixed = (vecs * vals) @ vecs.T
    d = np.sqrt(np.diag(fixed))
    fixed = fixed / np.outer(d, d)
    np.fill_diagonal(fixed, 1.0)
    return fixed


def build_cov(vols: pd.Series, corr: pd.DataFrame) -> pd.DataFrame:
    """Covariance from per-strategy daily R vols and a correlation matrix."""
    v = vols.reindex(corr.index).to_numpy(dtype=np.float64)
    return pd.DataFrame(corr.to_numpy() * np.outer(v, v), index=corr.index, columns=corr.columns)
