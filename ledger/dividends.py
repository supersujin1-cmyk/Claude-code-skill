"""7. 배당금: 월별 배당 캘린더(원화, 세후)."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable


@dataclass
class Dividend:
    paid_on: date
    symbol: str
    name: str
    amount: Decimal          # 세전, 지급 통화
    currency: str = "KRW"
    fx_rate: Decimal = Decimal(1)
    tax: Decimal = Decimal(0)  # 지급 통화

    @property
    def net_krw(self) -> Decimal:
        return (self.amount - self.tax) * self.fx_rate


def monthly_calendar(divs: Iterable[Dividend], year: int) -> dict[int, Decimal]:
    """1~12월 각각의 세후 배당(원). 배당 없는 달도 0으로."""
    out = {m: Decimal(0) for m in range(1, 13)}
    for d in divs:
        if d.paid_on.year == year:
            out[d.paid_on.month] += d.net_krw
    return out


def by_symbol(divs: Iterable[Dividend], year: int) -> dict[str, Decimal]:
    out: dict[str, Decimal] = defaultdict(Decimal)
    for d in divs:
        if d.paid_on.year == year:
            out[d.name] += d.net_krw
    return dict(sorted(out.items(), key=lambda kv: kv[1], reverse=True))
