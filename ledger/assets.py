from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping

from ledger.portfolio import Valuation

D = Decimal


@dataclass
class AssetBreakdown:
    cash: Decimal
    domestic_stock: Decimal
    foreign_stock: Decimal
    card_due: Decimal = D(0)  # 결제 예정 카드대금 (부채)

    @property
    def total(self) -> Decimal:
        return self.cash + self.domestic_stock + self.foreign_stock

    @property
    def net_worth(self) -> Decimal:
        return self.total - self.card_due

    def shares(self) -> dict[str, Decimal]:
        if not self.total:
            return {}
        parts = {"현금": self.cash, "국내주식": self.domestic_stock, "해외주식": self.foreign_stock}
        return {k: v / self.total * 100 for k, v in parts.items()}


def breakdown(
    cash_balances: Mapping[str, Decimal],
    valuations: Iterable[Valuation],
    card_due: Decimal = D(0),
) -> AssetBreakdown:
    dom = foreign = D(0)
    for v in valuations:
        if v.holding.currency == "KRW":
            dom += v.value_krw
        else:
            foreign += v.value_krw
    return AssetBreakdown(sum(cash_balances.values(), D(0)), dom, foreign, card_due)
