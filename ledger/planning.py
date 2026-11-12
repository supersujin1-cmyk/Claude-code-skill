"""예산, 저축률, 월말 지출 예측, 목표 저축."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Mapping

from ledger import summary
from ledger.models import Transaction

D = Decimal


# ---------- 1. 예산 ----------
@dataclass
class BudgetStatus:
    category: str
    budget: Decimal
    spent: Decimal

    @property
    def pct(self) -> Decimal:
        return self.spent / self.budget * 100 if self.budget else D(0)

    @property
    def remaining(self) -> Decimal:
        return self.budget - self.spent

    @property
    def level(self) -> str:  # ok | warn | over
        return "over" if self.pct > 100 else "warn" if self.pct >= 80 else "ok"


def budget_status(txs: Iterable[Transaction], budgets: Mapping[str, Decimal], today: date) -> list[BudgetStatus]:
    spent = summary.by_category(txs, today.replace(day=1), today)
    return [BudgetStatus(c, D(b), spent.get(c, D(0))) for c, b in budgets.items()]


# ---------- 4. 저축률 ----------
def savings_rate(income: Decimal, expense: Decimal) -> Decimal:
    return (income - expense) / income * 100 if income else D(0)


# ---------- 5. 이번 달 예상 지출 ----------
@dataclass
class Forecast:
    spent_so_far: Decimal
    projected: Decimal
    days_elapsed: int
    days_in_month: int


def month_forecast(
    txs: Iterable[Transaction],
    today: date,
    fixed_remaining: Decimal = D(0),
    exclude_from_pace: frozenset[str] | set[str] = frozenset(),
) -> Forecast:
    """남은 날은 '평소 지출' 하루 평균으로 채우고, 아직 안 나간 고정지출을 더합니다.

    exclude_from_pace: 고정지출·일회성 큰 결제처럼 속도 계산에서 뺄 거래 id. 이미 쓴 돈에는 포함됩니다.
    """
    txs = list(txs)
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    start = today.replace(day=1)
    spent = sum(summary.daily_expense(txs, start, today).values(), D(0))
    usual = [t for t in txs if t.id not in exclude_from_pace]
    pace = sum(summary.daily_expense(usual, start, today).values(), D(0)) / today.day
    elapsed = today.day
    projected = spent + pace * (days_in_month - elapsed) + fixed_remaining
    return Forecast(spent, projected, elapsed, days_in_month)


# ---------- 9. 목표 저축 ----------
@dataclass
class Goal:
    name: str
    target: Decimal
    saved: Decimal
    deadline: date

    @property
    def pct(self) -> Decimal:
        return min(self.saved / self.target * 100, D(100)) if self.target else D(100)

    def monthly_needed(self, today: date) -> Decimal:
        months = (self.deadline.year - today.year) * 12 + self.deadline.month - today.month
        left = max(self.target - self.saved, D(0))
        return left if months <= 0 else left / months
