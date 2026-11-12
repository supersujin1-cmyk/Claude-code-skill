from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


class TxKind(str, Enum):
    NORMAL = "normal"
    CARD_PAYMENT = "card_payment"  # 통장에서 나가는 카드대금: 카드 내역과 중복이므로 집계 제외
    TRANSFER = "transfer"          # 내 계좌끼리 옮긴 돈: 집계 제외


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class Transaction:
    account_id: str
    occurred_on: date
    amount: Decimal  # 원화. 출금 음수, 입금 양수
    description: str
    category: str = "미분류"
    kind: TxKind = TxKind.NORMAL
    seq: int = 0  # 같은 날 같은 금액·내용 거래를 구분하는 파일 내 순번
    id: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.id = content_id(
            self.account_id, self.occurred_on.isoformat(), str(self.amount), self.description, str(self.seq)
        )

    @property
    def counts_in_budget(self) -> bool:
        return self.kind == TxKind.NORMAL


@dataclass
class Trade:
    account_id: str
    traded_on: date
    symbol: str
    name: str
    side: Side
    quantity: Decimal
    price: Decimal          # 거래 통화 기준
    currency: str = "KRW"
    fx_rate: Decimal = Decimal("1")  # 거래 시점 1 통화단위 = ? 원
    fee: Decimal = Decimal("0")      # 거래 통화 기준 수수료+세금
    market: str = "KR"


def content_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]
