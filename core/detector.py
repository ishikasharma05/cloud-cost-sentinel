"""Rule-based cost anomaly detection (transparent thresholds, no ML).

A day is flagged only if it clears ALL three gates, which keeps tiny-dollar
noise from triggering alerts:
    1. z-score gate   : (cost - mean) / std >= z_threshold
    2. absolute gate  : cost - mean >= min_abs_increase  (dollars)
    3. relative gate  : cost >= mean * (1 + min_pct_increase)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from core.baseline import compute_baseline, group_series


@dataclass(frozen=True)
class Anomaly:
    provider: str
    service: str
    date: str
    cost: float
    baseline_mean: float
    baseline_std: float
    z_score: float
    pct_over_baseline: float

    def to_dict(self) -> dict:
        return asdict(self)


def detect_anomalies(
    records: list[dict],
    target_date: str | None = None,
    baseline_days: int = 7,
    min_history: int = 5,
    z_threshold: float = 3.0,
    min_abs_increase: float = 0.50,
    min_pct_increase: float = 0.30,
) -> list[Anomaly]:
    """Return anomalies for target_date (defaults to the newest date in the data)."""
    if not records:
        return []
    if target_date is None:
        target_date = max(r["date"] for r in records)

    found: list[Anomaly] = []
    for (provider, service), by_date in group_series(records).items():
        if target_date not in by_date:
            continue
        base = compute_baseline(by_date, target_date, baseline_days, min_history)
        if base is None:
            continue

        cost = by_date[target_date]
        increase = cost - base.mean
        z = increase / base.std
        pct = increase / base.mean if base.mean > 0 else float("inf")

        if z >= z_threshold and increase >= min_abs_increase and pct >= min_pct_increase:
            found.append(Anomaly(
                provider=provider, service=service, date=target_date,
                cost=round(cost, 4), baseline_mean=round(base.mean, 4),
                baseline_std=round(base.std, 4), z_score=round(z, 2),
                pct_over_baseline=round(pct * 100, 1) if pct != float("inf") else float("inf"),
            ))
    return sorted(found, key=lambda a: a.z_score, reverse=True)