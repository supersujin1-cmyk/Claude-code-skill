"""연말정산: 신용카드 등 소득공제 추정.

세법은 해마다 바뀝니다. 공제율과 한도는 `YearEndRules`에 모아 두었으니 매년 값만 확인해 바꾸세요.
여기 기본값은 2025년 귀속 기준의 일반 규정이며, 소비증가분 추가공제 같은 한시 특례는 넣지 않았습니다.
결과는 추정치이고 최종 금액은 국세청 연말정산 간소화 자료로 확인해야 합니다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable, Mapping

from ledger.models import Transaction, TxKind

D = Decimal

# 공제율이 낮은 순서. 25% 문턱은 이 순서대로 먼저 채워집니다.
GROUPS = ("credit", "debit", "culture", "market", "transit")
GROUP_LABELS = {
    "credit": "신용카드",
    "debit": "체크카드·현금영수증",
    "culture": "도서·공연·영화 등 문화",
    "market": "전통시장",
    "transit": "대중교통",
}


@dataclass(frozen=True)
class YearEndRules:
    threshold_ratio: Decimal = D("0.25")
    rates: Mapping[str, Decimal] = field(default_factory=lambda: {
        "credit": D("0.15"), "debit": D("0.30"), "culture": D("0.30"),
        "market": D("0.40"), "transit": D("0.40"),
    })
    culture_salary_cap: Decimal = D("70000000")  # 이 금액 이하만 문화비 30%
    basic_limit_low: Decimal = D("3000000")      # 총급여 7천만 이하
    basic_limit_high: Decimal = D("2500000")
    extra_limit_low: Decimal = D("3000000")      # 전통시장·대중교통·문화 추가한도
    extra_limit_high: Decimal = D("2000000")
    patterns: Mapping[str, tuple[str, ...]] = field(default_factory=lambda: {
        "transit": ("지하철", "버스", "코레일", "KTX", "SRT", "티머니", "캐시비", "교통카드"),
        "market": ("전통시장", "재래시장"),
        "culture": ("교보문고", "영풍문고", "알라딘", "YES24", "예스24", "CGV", "메가박스",
                    "롯데시네마", "인터파크티켓", "박물관", "미술관"),
    })


@dataclass
class DeductionEstimate:
    salary: Decimal
    spend: dict[str, Decimal]
    threshold: Decimal
    deduction: Decimal
    basic_limit: Decimal
    extra_limit: Decimal

    @property
    def total_spend(self) -> Decimal:
        return sum(self.spend.values(), D(0))

    @property
    def remaining_to_threshold(self) -> Decimal:
        return max(self.threshold - self.total_spend, D(0))

    @property
    def advice(self) -> str:
        if self.remaining_to_threshold > 0:
            return (f"공제 문턱(총급여의 25%)까지 {self.remaining_to_threshold:,.0f}원 남았습니다. "
                    "문턱 전에는 공제가 없으니 혜택이 큰 신용카드를 쓰는 편이 유리합니다.")
        if self.deduction >= self.basic_limit:
            return "기본 공제한도에 도달했습니다. 전통시장·대중교통·문화 지출만 추가로 공제됩니다."
        return "공제 문턱을 넘었습니다. 지금부터는 공제율이 2배인 체크카드·현금영수증이 유리합니다."


@dataclass(frozen=True)
class PensionRules:
    """8. 연금저축·IRP 세액공제. 2025년 귀속 일반 규정 기준이며 매년 확인하세요."""
    pension_limit: Decimal = D("6000000")      # 연금저축 단독 한도
    total_limit: Decimal = D("9000000")        # 연금저축 + IRP 합산 한도
    salary_cut: Decimal = D("55000000")        # 이하면 높은 공제율
    rate_high: Decimal = D("0.165")
    rate_low: Decimal = D("0.132")


@dataclass
class PensionEstimate:
    eligible: Decimal       # 공제 대상 납입액
    credit: Decimal         # 예상 세액공제(환급에 가까운 금액)
    room_left: Decimal      # 한도까지 더 넣을 수 있는 금액
    rate: Decimal


def pension_credit(salary: Decimal, pension: Decimal, irp: Decimal, rules: PensionRules = PensionRules()) -> PensionEstimate:
    eligible = min(min(pension, rules.pension_limit) + irp, rules.total_limit)
    rate = rules.rate_high if salary <= rules.salary_cut else rules.rate_low
    return PensionEstimate(eligible, eligible * rate, rules.total_limit - eligible, rate)


def classify(description: str, payment_type: str, rules: YearEndRules) -> str:
    text = description.upper()
    for group in ("transit", "market", "culture"):
        if any(p.upper() in text for p in rules.patterns[group]):
            return group
    return "credit" if payment_type == "credit" else "debit"


def spend_by_group(
    txs: Iterable[Transaction],
    year: int,
    card_payment_types: Mapping[str, str],
    rules: YearEndRules = YearEndRules(),
) -> dict[str, Decimal]:
    """card_payment_types: 카드 계좌 id → 'credit' | 'debit'. 그 외 계좌는 무시."""
    out = {g: D(0) for g in GROUPS}
    for t in txs:
        ptype = card_payment_types.get(t.account_id)
        if ptype is None or t.occurred_on.year != year or t.kind != TxKind.NORMAL:
            continue
        # 카드 취소(양수)는 같은 그룹에서 빼 줍니다.
        out[classify(t.description, ptype, rules)] -= t.amount
    return {g: max(v, D(0)) for g, v in out.items()}


def estimate(salary: Decimal, spend: Mapping[str, Decimal], rules: YearEndRules = YearEndRules()) -> DeductionEstimate:
    spend = {g: D(spend.get(g, 0)) for g in GROUPS}
    low = salary <= rules.culture_salary_cap
    if not low:  # 고소득자는 문화비 별도 공제율 없음 → 신용카드로 취급
        spend["credit"] += spend["culture"]
        spend["culture"] = D(0)

    threshold = salary * rules.threshold_ratio
    left = threshold
    ded_by_group: dict[str, Decimal] = {}
    for g in GROUPS:
        used = min(spend[g], left)
        left -= used
        ded_by_group[g] = (spend[g] - used) * rules.rates[g]

    total = sum(ded_by_group.values(), D(0))
    basic_limit = rules.basic_limit_low if low else rules.basic_limit_high
    extra_limit = rules.extra_limit_low if low else rules.extra_limit_high
    special = ded_by_group["market"] + ded_by_group["transit"] + ded_by_group["culture"]
    basic = min(total, basic_limit)
    extra = min(total - basic, special, extra_limit)
    return DeductionEstimate(salary, spend, threshold, basic + extra, basic_limit, extra_limit)
