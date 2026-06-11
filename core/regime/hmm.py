"""GaussianHMM regime layer (hmmlearn).

Fits an HMM on standardized regime features with multiple random restarts,
keeping the best log-likelihood. States are given interpretable names by
majority vote of the rule-based labels falling in each state.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

DEFAULT_FEATURES = ("adx", "r2", "atr_pctile", "volvol_pctile", "hurst", "efficiency_ratio", "ret_1")


@dataclass(frozen=True)
class HMMRegimeModel:
    model: GaussianHMM
    feature_cols: tuple[str, ...]
    mean: np.ndarray
    std: np.ndarray
    log_likelihood: float
    states: pd.Series  # state id per bar (aligned to the dropna'd index)
    transition_matrix: np.ndarray
    state_names: dict[int, str]  # state id -> majority rule label

    def to_dict(self) -> dict:
        return {
            "n_states": int(self.model.n_components),
            "log_likelihood": self.log_likelihood,
            "transition_matrix": self.transition_matrix.tolist(),
            "state_names": {int(k): v for k, v in self.state_names.items()},
            "stationary_distribution": _stationary(self.transition_matrix).tolist(),
        }


def _stationary(P: np.ndarray) -> np.ndarray:
    vals, vecs = np.linalg.eig(P.T)
    i = int(np.argmin(np.abs(vals - 1.0)))
    v = np.real(vecs[:, i])
    v = np.abs(v)
    return v / v.sum()


def fit_hmm(
    features: pd.DataFrame,
    rule_labels: pd.Series | None = None,
    n_states: int = 4,
    n_restarts: int = 10,
    n_iter: int = 200,
    seed: int = 42,
    feature_cols: tuple[str, ...] = DEFAULT_FEATURES,
) -> HMMRegimeModel:
    """Fit a GaussianHMM with `n_restarts` random restarts; keep the best LL."""
    cols = [c for c in feature_cols if c in features.columns]
    X_df = features[cols].dropna()
    if len(X_df) < n_states * 20:
        raise ValueError("not enough feature rows to fit HMM")
    X = X_df.to_numpy(dtype=np.float64)
    mean, std = X.mean(axis=0), X.std(axis=0)
    std[std < 1e-12] = 1.0
    Xz = (X - mean) / std

    best: GaussianHMM | None = None
    best_ll = -np.inf
    for k in range(n_restarts):
        m = GaussianHMM(n_components=n_states, covariance_type="diag",
                        n_iter=n_iter, random_state=seed + k)
        try:
            m.fit(Xz)
            ll = float(m.score(Xz))
        except (ValueError, np.linalg.LinAlgError):
            continue
        if ll > best_ll:
            best, best_ll = m, ll
    if best is None:
        raise RuntimeError("all HMM restarts failed")

    states = pd.Series(best.predict(Xz), index=X_df.index, name="hmm_state")

    state_names: dict[int, str] = {}
    if rule_labels is not None:
        aligned = rule_labels.reindex(X_df.index)
        for s in range(n_states):
            labels = aligned[states == s]
            state_names[s] = str(labels.mode().iloc[0]) if len(labels) else f"STATE_{s}"
    else:
        state_names = {s: f"STATE_{s}" for s in range(n_states)}

    return HMMRegimeModel(
        model=best, feature_cols=tuple(cols), mean=mean, std=std,
        log_likelihood=best_ll, states=states,
        transition_matrix=np.asarray(best.transmat_), state_names=state_names,
    )
