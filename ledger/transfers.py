"""이중 계산 방지: 카드대금 출금과 내 계좌 간 이체를 집계에서 뺍니다."""
from __future__ import annotations

from typing import Iterable, Sequence

from ledger.models import Transaction, TxKind

DEFAULT_CARD_PAYMENT_PATTERNS = ("국민카드", "KB카드", "삼성카드")


def mark_card_payments(
    txs: Iterable[Transaction],
    bank_account_ids: set[str],
    patterns: Sequence[str] = DEFAULT_CARD_PAYMENT_PATTERNS,
) -> None:
    """통장 출금 중 카드사 이름이 들어간 것은 카드대금으로 표시."""
    for tx in txs:
        if tx.account_id in bank_account_ids and tx.amount < 0 and any(
            p.upper() in tx.description.upper() for p in patterns
        ):
            tx.kind = TxKind.CARD_PAYMENT
            tx.category = "카드대금"


def mark_transfers_by_pattern(txs: Iterable[Transaction], patterns: Sequence[str]) -> None:
    """상대 계좌 내역이 없는 내 계좌 이체(예: 은행 → KB증권)를 내용으로 표시."""
    for tx in txs:
        if tx.kind == TxKind.NORMAL and any(p.upper() in tx.description.upper() for p in patterns):
            tx.kind = TxKind.TRANSFER
            tx.category = "이체"


def mark_internal_transfers(txs: Sequence[Transaction], max_days: int = 1) -> None:
    """서로 다른 내 계좌에서 같은 금액이 나가고 들어온 쌍을 이체로 표시."""
    outs = [t for t in txs if t.amount < 0 and t.kind == TxKind.NORMAL]
    ins = [t for t in txs if t.amount > 0 and t.kind == TxKind.NORMAL]
    used: set[str] = set()
    for out in sorted(outs, key=lambda t: t.occurred_on):
        for inc in sorted(ins, key=lambda t: t.occurred_on):
            if (
                inc.id not in used
                and inc.account_id != out.account_id
                and inc.amount == -out.amount
                and abs((inc.occurred_on - out.occurred_on).days) <= max_days
            ):
                for t in (out, inc):
                    t.kind = TxKind.TRANSFER
                    t.category = "이체"
                used.add(inc.id)
                break
