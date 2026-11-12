"""6. 카드 실적: 이번 달 사용액이 카드 혜택 조건(전월 실적)을 채웠는지."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Mapping

from ledger.models import Transaction


@dataclass
class CardPerformance:
    account_id: str
    name: str
    required: Decimal
    spent: Decimal
    days_left: int

    @property
    def remaining(self) -> Decimal:
        return max(self.required - self.spent, Decimal(0))

    @property
    def pct(self) -> Decimal:
        return min(self.spent / self.required * 100, Decimal(100)) if self.required else Decimal(100)


def card_performance(
    txs: Iterable[Transaction],
    cards: Mapping[str, tuple[str, Decimal]],  # 계좌 id → (카드 이름, 필요 실적)
    today: date,
) -> list[CardPerformance]:
    spent = {cid: Decimal(0) for cid in cards}
    for t in txs:
        if t.account_id in cards and t.counts_in_budget and (t.occurred_on.year, t.occurred_on.month) == (
            today.year, today.month
        ):
            spent[t.account_id] -= t.amount  # 결제는 음수, 취소는 양수
    days_left = calendar.monthrange(today.year, today.month)[1] - today.day
    return [CardPerformance(cid, name, req, spent[cid], days_left) for cid, (name, req) in cards.items()]
