"""2. 고정지출·구독 자동 찾기: 매달 비슷한 금액으로 반복되는 출금."""
from __future__ import annotations

import re
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from ledger.models import Transaction


@dataclass
class Recurring:
    name: str
    amount: Decimal       # 최근 금액
    day_of_month: int     # 보통 나가는 날
    months: int           # 몇 달 연속 확인됐는지
    last_date: date
    category: str

    def charged_this_month(self, today: date) -> bool:
        return (self.last_date.year, self.last_date.month) == (today.year, today.month)


def key(description: str) -> str:
    """'넷플릭스 11월분' 과 '넷플릭스 10월분' 을 같은 항목으로 묶기 위해 숫자와 공백을 뺍니다."""
    return re.sub(r"[\d\s\-_/.()]+|월분", "", description).upper()


def find_recurring(txs: Iterable[Transaction], min_months: int = 3, tolerance: float = 0.1) -> list[Recurring]:
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for t in txs:
        if t.counts_in_budget and t.amount < 0:
            groups[key(t.description)].append(t)

    found = []
    for items in groups.values():
        by_month = {}
        for t in sorted(items, key=lambda t: t.occurred_on):
            by_month[(t.occurred_on.year, t.occurred_on.month)] = t  # 한 달에 여러 번이면 반복 아님
        if len(by_month) < min_months or len(items) > len(by_month) * 1.5:
            continue
        amounts = [float(-t.amount) for t in by_month.values()]
        mean = statistics.mean(amounts)
        if mean == 0 or (max(amounts) - min(amounts)) / mean > tolerance * 2:
            continue
        last = max(by_month.values(), key=lambda t: t.occurred_on)
        day = round(statistics.median(t.occurred_on.day for t in by_month.values()))
        found.append(Recurring(last.description, -last.amount, day, len(by_month), last.occurred_on, last.category))
    return sorted(found, key=lambda r: r.amount, reverse=True)
