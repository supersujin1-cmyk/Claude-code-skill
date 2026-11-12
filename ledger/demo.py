"""화면 미리보기용 가짜 데이터. 실제 금융 정보가 아닙니다."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from ledger.brokers import FakeBrokerClient
from ledger.categorize import apply_categories
from ledger.dividends import Dividend
from ledger.models import Trade, Transaction
from ledger.planning import Goal
from ledger.transfers import mark_card_payments, mark_internal_transfers, mark_transfers_by_pattern

D = Decimal
KB_CARD, SAMSUNG_CARD, KB_BANK = "demo-kb-card", "demo-samsung-card", "demo-kb-bank"
CARD_PAYMENT_TYPES = {KB_CARD: "debit", SAMSUNG_CARD: "credit"}

_MERCHANTS = [
    ("스타벅스 강남점", 4500, 7000), ("배달의민족", 15000, 35000), ("GS25 역삼점", 2000, 9000),
    ("이마트 성수점", 20000, 70000), ("지하철 교통카드", 1400, 1600), ("버스 교통카드", 1500, 1500),
    ("쿠팡", 10000, 80000), ("교보문고", 12000, 30000), ("CGV 용산", 14000, 30000),
    ("카카오택시", 6000, 20000), ("망원 전통시장", 5000, 30000),
]
# (이름, 금액, 매달 나가는 날, 카드)
_SUBSCRIPTIONS = [
    ("넷플릭스", 17000, 5, SAMSUNG_CARD), ("유튜브 프리미엄", 14900, 10, SAMSUNG_CARD),
    ("SKT 통신요금", 65000, 21, KB_CARD), ("현대해상 보험료", 89000, 20, KB_CARD),
]


@dataclass
class DemoData:
    transactions: list[Transaction]
    trades: list[Trade]
    cash_balances: dict[str, Decimal]
    card_due: Decimal
    dividends: list[Dividend] = field(default_factory=list)
    networth_history: list[tuple[str, Decimal]] = field(default_factory=list)
    # 사용자가 화면에서 정하는 설정값
    budgets: dict[str, Decimal] = field(default_factory=dict)
    goals: list[Goal] = field(default_factory=list)
    card_requirements: dict[str, tuple[str, Decimal]] = field(default_factory=dict)
    salary: Decimal = D(45_600_000)
    pension_paid: Decimal = D(0)
    irp_paid: Decimal = D(0)


def build(today: date, seed: int = 7) -> DemoData:
    rng = random.Random(seed)
    txs: list[Transaction] = []
    d = date(today.year - 1, 12, 1)
    seq = 0
    while d <= today:
        for _ in range(rng.randint(1, 4)):
            name, lo, hi = rng.choice(_MERCHANTS)
            seq += 1
            txs.append(Transaction(rng.choice([KB_CARD, SAMSUNG_CARD]), d, -D(rng.randrange(lo, hi + 1, 100)),
                                   name, seq=seq))
        for name, amt, day, card in _SUBSCRIPTIONS:
            if d.day == day:
                txs.append(Transaction(card, d, -D(amt), name))
        if d.day == 25:
            txs.append(Transaction(KB_BANK, d, D(3_800_000), "급여 (주)데모회사"))
            txs.append(Transaction(KB_BANK, d, D(-500_000), "KB증권 이체"))
        if d.day == 15:
            txs.append(Transaction(KB_BANK, d, D(-900_000), "삼성카드 결제대금"))
            txs.append(Transaction(KB_BANK, d, D(-450_000), "KB국민카드 결제"))
            txs.append(Transaction(KB_BANK, d, D(-700_000), "월세"))
        d += timedelta(days=1)
    # 이상 지출 예시: 처음 보는 가게의 큰 결제
    txs.append(Transaction(SAMSUNG_CARD, today - timedelta(days=3), D(-890_000), "하이마트 온라인몰"))

    mark_card_payments(txs, {KB_BANK})
    mark_transfers_by_pattern(txs, ["KB증권"])
    mark_internal_transfers(txs)
    apply_categories(txs)

    y = today.year
    dividends = [
        Dividend(date(y, 4, 18), "005930", "삼성전자", D(361) * 20, tax=D(361) * 20 * D("0.154")),
        Dividend(date(y, 5, 16), "AAPL", "Apple", D("0.26") * 5, "USD", D(1370), D("0.26") * 5 * D("0.15")),
        Dividend(date(y, 5, 20), "005930", "삼성전자", D(361) * 20, tax=D(361) * 20 * D("0.154")),
        Dividend(date(y, 8, 14), "AAPL", "Apple", D("0.26") * 5, "USD", D(1385), D("0.26") * 5 * D("0.15")),
        Dividend(date(y, 8, 20), "005930", "삼성전자", D(361) * 20, tax=D(361) * 20 * D("0.154")),
        Dividend(date(y, 11, 10), "AAPL", "Apple", D("0.26") * 3, "USD", D(1400), D("0.26") * 3 * D("0.15")),
    ]
    networth = D(9_738_000)
    history = []
    for i in range(12):
        m = (today.month - 1 - i) % 12 + 1
        yy = today.year - (1 if today.month - 1 - i < 0 else 0)
        history.append((f"{yy}-{m:02d}", networth))
        networth -= D(rng.randrange(150_000, 650_000, 10_000))
    history.reverse()

    return DemoData(
        transactions=txs,
        trades=FakeBrokerClient().fetch_trades(date(2000, 1, 1), today),
        cash_balances={KB_BANK: D(8_420_000)},
        card_due=D(1_250_000),
        dividends=dividends,
        networth_history=history,
        budgets={"식비": D(300_000), "카페": D(60_000), "장보기": D(400_000), "쇼핑": D(200_000),
                 "교통": D(100_000), "문화": D(80_000)},
        goals=[Goal("여행 자금", D(3_000_000), D(1_850_000), date(y + 1, 3, 31)),
               Goal("비상금", D(10_000_000), D(6_200_000), date(y + 1, 12, 31))],
        card_requirements={KB_CARD: ("KB국민카드", D(300_000)), SAMSUNG_CARD: ("삼성카드", D(500_000))},
        pension_paid=D(3_600_000), irp_paid=D(1_000_000),
    )
