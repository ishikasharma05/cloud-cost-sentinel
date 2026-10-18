"""Rolling-baseline statistics for per-service daily cost series.

Input is the normalized record shape every adapter produces:
    {"provider": "aws", "service": "Amazon EC2", "date": "2026-09-13", "cost": 4.32}
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean, pstdev


@dataclass(frozen=True)
class Baseline:
    mean: float
    std: float
    days: int


def group_series(records: list[dict]) -> dict[tuple[str, str], dict[str, float]]:
    """Group records into {(provider, service): {date: total_cost}}."""
    series: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in records:
        series[(r["provider"], r["service"])][r["date"]] += float(r["cost"])
    return series


def compute_baseline(
    by_date: dict[str, float],
    target_date: str,
    window: int = 7,
    min_history: int = 5,
    std_floor: float = 0.01,
) -> Baseline | None:
    """Baseline from the `window` days BEFORE target_date.

    Returns None if there isn't enough history to say anything useful.
    std_floor stops a perfectly flat baseline (std=0) from exploding z-scores.
    """
    prior = sorted(d for d in by_date if d < target_date)[-window:]  # ISO dates sort as strings
    if len(prior) < min_history:
        return None
    values = [by_date[d] for d in prior]
    return Baseline(mean=mean(values), std=max(pstdev(values), std_floor), days=len(values))