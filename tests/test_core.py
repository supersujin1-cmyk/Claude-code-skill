from datetime import date
from decimal import Decimal as D

import pytest

from ledger import assets, demo, summary, yearend
from ledger.categorize import apply_categories
from ledger.models import Side, Trade, Transaction, TxKind
from ledger.portfolio import build_holdings, value_holdings
from ledger.transfers import mark_card_payments, mark_internal_transfers


def tx(acc, day, amount, desc, seq=0):
    return Transaction(acc, date(2026, 11, day), D(amount), desc, seq=seq)


def test_same_content_gets_same_id_for_dedup():
    assert tx("a", 1, -100, "x").id == tx("a", 1, -100, "x").id
    assert tx("a", 1, -100, "x").id != tx("a", 1, -100, "x", seq=1).id


def test_categorize_and_income_default():
    txs = [tx("c", 1, -4500, "스타벅스 강남"), tx("c", 1, -100, "알수없음"), tx("b", 1, 1000, "이자")]
    apply_categories(txs)
    assert [t.category for t in txs] == ["카페", "미분류", "수입"]


def test_card_payment_and_internal_transfer_excluded_from_budget():
    pay = tx("bank", 15, -900000, "삼성카드 결제대금")
    out = tx("bank", 3, -500000, "이체")
    inc = tx("bank2", 3, 500000, "이체")
    spend = tx("card", 3, -10000, "GS25")
    txs = [pay, out, inc, spend]
    mark_card_payments(txs, {"bank"})
    mark_internal_transfers(txs)
    assert pay.kind == TxKind.CARD_PAYMENT
    assert out.kind == inc.kind == TxKind.TRANSFER
    assert [m.expense for m in summary.monthly(txs)] == [D(10000)]


def test_weekly_groups_by_monday():
    txs = [tx("c", 9, -100, "a"), tx("c", 15, -200, "b"), tx("c", 16, -300, "c")]  # 11/9 월, 11/15 일, 11/16 월
    rows = summary.weekly(txs)
    assert [(r.label, r.expense) for r in rows] == [("2026-11-09", D(300)), ("2026-11-16", D(300))]


def test_portfolio_average_cost_realized_and_fx():
    trades = [
        Trade("k", date(2026, 1, 1), "AAPL", "Apple", Side.BUY, D(10), D(100), "USD", D(1300)),
        Trade("k", date(2026, 2, 1), "AAPL", "Apple", Side.BUY, D(10), D(200), "USD", D(1400)),
        Trade("k", date(2026, 3, 1), "AAPL", "Apple", Side.SELL, D(10), D(250), "USD", D(1500)),
    ]
    h = build_holdings(trades)["AAPL"]
    assert h.quantity == 10
    assert h.avg_price == D(150)
    # 매입원가(원): 1,300,000 + 2,800,000 = 4,100,000 → 절반 매도분 2,050,000
    assert h.cost_krw == D(2050000)
    assert h.realized_krw == D(10) * 250 * 1500 - D(2050000)
    [v] = value_holdings({"AAPL": h}, {"AAPL": D(300)}, {"USD": D(1400)})
    assert v.value_krw == D(4200000)


def test_sell_more_than_held_raises():
    with pytest.raises(ValueError):
        build_holdings([Trade("k", date(2026, 1, 1), "X", "X", Side.SELL, D(1), D(1))])


def test_yearend_below_threshold_has_no_deduction():
    est = yearend.estimate(D(40_000_000), {"credit": D(5_000_000)})
    assert est.deduction == 0
    assert est.remaining_to_threshold == D(5_000_000)


def test_yearend_threshold_consumes_credit_first():
    # 문턱 1,000만: 신용 1,200만으로 채우고 남은 200만*15% + 체크 300만*30% = 30만 + 90만
    est = yearend.estimate(D(40_000_000), {"credit": D(12_000_000), "debit": D(3_000_000)})
    assert est.deduction == D(1_200_000)


def test_yearend_limits_with_extra_for_transit():
    est = yearend.estimate(D(40_000_000), {"debit": D(30_000_000), "transit": D(5_000_000)})
    # 체크 (3,000만-1,000만)*30% = 600만, 교통 200만 → 기본 300만 + 추가 min(500만, 200만, 300만)
    assert est.deduction == D(5_000_000)


def test_yearend_classify():
    rules = yearend.YearEndRules()
    assert yearend.classify("지하철 교통카드", "credit", rules) == "transit"
    assert yearend.classify("스타벅스", "debit", rules) == "debit"


def test_assets_breakdown():
    trades = [Trade("k", date(2026, 1, 1), "005930", "삼성전자", Side.BUY, D(1), D(70000))]
    vals = value_holdings(build_holdings(trades), {"005930": D(80000)}, {})
    ab = assets.breakdown({"bank": D(20000)}, vals, card_due=D(10000))
    assert (ab.total, ab.net_worth, ab.shares()["국내주식"]) == (D(100000), D(90000), D(80))


def test_demo_builds_and_salary_is_income():
    data = demo.build(date(2026, 11, 12))
    assert any(t.category == "수입" for t in data.transactions)
    assert all(t.kind == TxKind.TRANSFER for t in data.transactions if "KB증권" in t.description)
