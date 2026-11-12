from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from ledger.models import Transaction


@dataclass
class PeriodSummary:
    label: str  # 월: "2026-11", 주: 그 주 월요일 "2026-11-09"
    income: Decimal
    expense: Decimal  # 양수로 표시

    @property
    def net(self) -> Decimal:
        return self.income - self.expense


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _summarize(txs: Iterable[Transaction], key) -> list[PeriodSummary]:
    inc: dict[str, Decimal] = defaultdict(Decimal)
    exp: dict[str, Decimal] = defaultdict(Decimal)
    for t in txs:
        if not t.counts_in_budget:
            continue
        k = key(t.occurred_on)
        if t.amount > 0:
            inc[k] += t.amount
        else:
            exp[k] += -t.amount
    return [PeriodSummary(k, inc[k], exp[k]) for k in sorted(set(inc) | set(exp))]


def monthly(txs: Iterable[Transaction]) -> list[PeriodSummary]:
    return _summarize(txs, lambda d: d.strftime("%Y-%m"))


def weekly(txs: Iterable[Transaction]) -> list[PeriodSummary]:
    return _summarize(txs, lambda d: week_start(d).isoformat())


def daily_expense(txs: Iterable[Transaction], start: date, end: date) -> dict[date, Decimal]:
    """start~end(포함) 날짜별 지출. 지출 없는 날도 0으로 포함."""
    out = {start + timedelta(days=i): Decimal(0) for i in range((end - start).days + 1)}
    for t in txs:
        if t.counts_in_budget and t.amount < 0 and t.occurred_on in out:
            out[t.occurred_on] += -t.amount
    return out


def by_category(txs: Iterable[Transaction], start: date, end: date) -> dict[str, Decimal]:
    out: dict[str, Decimal] = defaultdict(Decimal)
    for t in txs:
        if t.counts_in_budget and t.amount < 0 and start <= t.occurred_on <= end:
            out[t.category] += -t.amount
    return dict(sorted(out.items(), key=lambda kv: kv[1], reverse=True))
