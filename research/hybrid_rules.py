"""Phase 15: the fixed rules that combine two risk signals into one.

Each rule takes two score arrays (higher = riskier) and returns one score array.
They use the scores only, never the labels, and have no tunable weights, so
there is nothing to fit on the test set. The design is declared in
docs/PROJECT_BIBLE.md (Phase 15).
"""
import numpy as np
import pandas as pd


def pct_rank(x) -> np.ndarray:
    """Percentile rank in (0, 1]: the lowest score gets about 1/n, the highest gets 1.
    Equal scores share the average rank."""
    return pd.Series(np.asarray(x, dtype=float)).rank(method="average").to_numpy() / len(x)


def rank_average(a, b) -> np.ndarray:
    """Primary hybrid (P): both signals count equally."""
    return (pct_rank(a) + pct_rank(b)) / 2


def tie_break(main, second) -> np.ndarray:
    """S1: order PRs by `main`; `second` only separates PRs whose `main` is equal.
    Different values of `main` differ by at least 1 in average rank, and the
    `second` bonus is at most 0.5, so it can never overtake a real difference."""
    main_rank = pd.Series(np.asarray(main, dtype=float)).rank(method="average").to_numpy()
    return main_rank + 0.5 * pct_rank(second)


def higher_of(a, b) -> np.ndarray:
    """S2: a PR is as risky as the more worried of the two signals says."""
    return np.maximum(pct_rank(a), pct_rank(b))
