from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ledger.models import Transaction, TxKind

UNCATEGORIZED = "미분류"
INCOME = "수입"


@dataclass(frozen=True)
class Rule:
    pattern: str
    category: str
    priority: int = 100  # 숫자가 작을수록 먼저 적용


DEFAULT_RULES: tuple[Rule, ...] = (
    Rule("스타벅스", "카페"),
    Rule("투썸", "카페"),
    Rule("이디야", "카페"),
    Rule("배달의민족", "식비"),
    Rule("쿠팡이츠", "식비"),
    Rule("요기요", "식비"),
    Rule("이마트", "장보기"),
    Rule("홈플러스", "장보기"),
    Rule("GS25", "편의점"),
    Rule("CU", "편의점", priority=200),
    Rule("세븐일레븐", "편의점"),
    Rule("쿠팡", "쇼핑", priority=150),
    Rule("네이버페이", "쇼핑", priority=150),
    Rule("전통시장", "장보기"),
    Rule("교보문고", "문화"),
    Rule("영풍문고", "문화"),
    Rule("CGV", "문화"),
    Rule("메가박스", "문화"),
    Rule("넷플릭스", "구독"),
    Rule("유튜브", "구독"),
    Rule("보험", "보험"),
    Rule("하이마트", "가전·가구", priority=50),  # "이마트"보다 먼저
    Rule("월세", "주거"),
    Rule("관리비", "주거"),
    Rule("택시", "교통"),
    Rule("지하철", "교통"),
    Rule("버스", "교통"),
    Rule("SKT", "통신"),
    Rule("KT", "통신", priority=200),
    Rule("LGU+", "통신"),
    Rule("급여", INCOME),
    Rule("월급", INCOME),
)


def categorize(tx: Transaction, rules: Iterable[Rule] = DEFAULT_RULES) -> str:
    text = tx.description.upper()
    for rule in sorted(rules, key=lambda r: r.priority):
        if rule.pattern.upper() in text:
            return rule.category
    return INCOME if tx.amount > 0 else UNCATEGORIZED


def apply_categories(txs: Iterable[Transaction], rules: Iterable[Rule] = DEFAULT_RULES) -> None:
    rules = tuple(rules)
    for tx in txs:
        if tx.kind == TxKind.NORMAL and tx.category == UNCATEGORIZED:
            tx.category = categorize(tx, rules)
