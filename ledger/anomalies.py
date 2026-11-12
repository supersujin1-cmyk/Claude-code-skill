"""10. 이상 지출: 평소보다 훨씬 큰 결제, 처음 보는 가게의 큰 결제."""
from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from ledger.models import Transaction


@dataclass
class Anomaly:
    tx: Transaction
    reason: str


def find_anomalies(
    txs: Iterable[Transaction],
    today: date,
    days: int = 14,
    new_merchant_min: Decimal = Decimal(50_000),
    sigma: float = 3.0,
) -> list[Anomaly]:
    spend = sorted((t for t in txs if t.counts_in_budget and t.amount < 0), key=lambda t: t.occurred_on)
    since = today - timedelta(days=days)
    history_by_cat: dict[str, list[float]] = defaultdict(list)
    seen: set[str] = set()
    out = []
    for t in spend:
        amt = float(-t.amount)
        if t.occurred_on > since:
            hist = history_by_cat[t.category]
            if t.description not in seen and amt >= float(new_merchant_min):
                out.append(Anomaly(t, "처음 보는 가게의 큰 결제"))
            elif len(hist) >= 5:
                mean, sd = statistics.mean(hist), statistics.pstdev(hist)
                # 평소 금액이 늘 같으면 표준편차가 0이므로, 평균의 3배 이상이라는 조건을 함께 씁니다.
                if amt > mean + sigma * sd and amt >= mean * 3:
                    out.append(Anomaly(t, f"{t.category} 평소 결제({mean:,.0f}원)보다 훨씬 큼"))
        history_by_cat[t.category].append(amt)
        seen.add(t.description)
    return sorted(out, key=lambda a: a.tx.occurred_on, reverse=True)
