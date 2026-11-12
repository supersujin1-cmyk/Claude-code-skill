"""투자 계산: 이동평균 단가, 실현손익, 원화 평가(해외주식 포함)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping

from ledger.models import Side, Trade

ZERO = Decimal("0")


@dataclass
class Holding:
    symbol: str
    name: str
    currency: str
    quantity: Decimal = ZERO
    cost: Decimal = ZERO       # 보유분 매입원가, 거래 통화
    cost_krw: Decimal = ZERO   # 보유분 매입원가, 원화(매수 시점 환율)
    realized_krw: Decimal = ZERO

    @property
    def avg_price(self) -> Decimal:
        return self.cost / self.quantity if self.quantity else ZERO


@dataclass
class Valuation:
    holding: Holding
    price: Decimal
    fx_rate: Decimal

    @property
    def value_krw(self) -> Decimal:
        return self.holding.quantity * self.price * self.fx_rate

    @property
    def unrealized_krw(self) -> Decimal:
        return self.value_krw - self.holding.cost_krw

    @property
    def return_pct(self) -> Decimal:
        c = self.holding.cost_krw
        return self.unrealized_krw / c * 100 if c else ZERO


def build_holdings(trades: Iterable[Trade]) -> dict[str, Holding]:
    holdings: dict[str, Holding] = {}
    for t in sorted(trades, key=lambda t: t.traded_on):
        h = holdings.setdefault(t.symbol, Holding(t.symbol, t.name, t.currency))
        if t.side == Side.BUY:
            gross = t.quantity * t.price + t.fee
            h.quantity += t.quantity
            h.cost += gross
            h.cost_krw += gross * t.fx_rate
        else:
            if t.quantity > h.quantity:
                raise ValueError(f"{t.symbol}: 보유 수량({h.quantity})보다 많이 매도({t.quantity})")
            ratio = t.quantity / h.quantity
            sold_cost, sold_cost_krw = h.cost * ratio, h.cost_krw * ratio
            proceeds_krw = (t.quantity * t.price - t.fee) * t.fx_rate
            h.realized_krw += proceeds_krw - sold_cost_krw
            h.quantity -= t.quantity
            h.cost -= sold_cost
            h.cost_krw -= sold_cost_krw
    return holdings


def value_holdings(
    holdings: Mapping[str, Holding],
    prices: Mapping[str, Decimal],
    fx_rates: Mapping[str, Decimal],
) -> list[Valuation]:
    """prices: 종목별 현재가(거래 통화). fx_rates: 통화별 현재 환율(KRW는 1)."""
    out = []
    for h in holdings.values():
        if h.quantity == 0:
            continue
        rate = Decimal("1") if h.currency == "KRW" else fx_rates[h.currency]
        out.append(Valuation(h, prices[h.symbol], rate))
    return out
