"""화면 미리보기용 가짜 데이터. 실제 금융 정보가 아닙니다."""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from ledger.brokers import FakeBrokerClient
from ledger.categorize import apply_categories
from ledger.models import Trade, Transaction
from ledger.transfers import mark_card_payments, mark_internal_transfers, mark_transfers_by_pattern

KB_CARD, SAMSUNG_CARD, KB_BANK = "demo-kb-card", "demo-samsung-card", "demo-kb-bank"
CARD_PAYMENT_TYPES = {KB_CARD: "debit", SAMSUNG_CARD: "credit"}

_MERCHANTS = [
    ("스타벅스 강남점", 4500, 7000), ("배달의민족", 15000, 35000), ("GS25 역삼점", 2000, 9000),
    ("이마트 성수점", 30000, 120000), ("지하철 교통카드", 1400, 1600), ("버스 교통카드", 1500, 1500),
    ("쿠팡", 10000, 80000), ("교보문고", 12000, 30000), ("CGV 용산", 14000, 30000),
    ("카카오택시", 6000, 20000), ("망원 전통시장", 5000, 30000), ("SKT 통신요금", 65000, 65000),
]


@dataclass
class DemoData:
    transactions: list[Transaction]
    trades: list[Trade]
    cash_balances: dict[str, Decimal]
    card_due: Decimal


def build(today: date, weeks: int = 12, seed: int = 7) -> DemoData:
    rng = random.Random(seed)
    txs: list[Transaction] = []
    start = today - timedelta(weeks=weeks)
    jan1 = date(today.year, 1, 1)
    d = min(start, jan1)
    seq = 0
    while d <= today:
        for _ in range(rng.randint(1, 4)):
            name, lo, hi = rng.choice(_MERCHANTS)
            amount = Decimal(rng.randrange(lo, hi + 1, 100))
            card = rng.choice([KB_CARD, SAMSUNG_CARD])
            seq += 1
            txs.append(Transaction(card, d, -amount, name, seq=seq))
        if d.day == 25:
            txs.append(Transaction(KB_BANK, d, Decimal(3_800_000), "급여 (주)데모회사"))
            txs.append(Transaction(KB_BANK, d, Decimal(-500_000), "KB증권 이체"))
        if d.day == 15:
            txs.append(Transaction(KB_BANK, d, Decimal(-900_000), "삼성카드 결제대금"))
            txs.append(Transaction(KB_BANK, d, Decimal(-450_000), "KB국민카드 결제"))
            txs.append(Transaction(KB_BANK, d, Decimal(-700_000), "월세"))
        d += timedelta(days=1)

    mark_card_payments(txs, {KB_BANK})
    mark_transfers_by_pattern(txs, ["KB증권"])
    mark_internal_transfers(txs)
    apply_categories(txs)

    trades = FakeBrokerClient().fetch_trades(date(2000, 1, 1), today)
    return DemoData(txs, trades, {KB_BANK: Decimal(8_420_000)}, Decimal(1_250_000))
