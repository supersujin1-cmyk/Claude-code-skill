from datetime import date
from decimal import Decimal as D

from ledger import anomalies, cards, demo, dividends, export, planning, recurring, yearend
from ledger.categorize import apply_categories
from ledger.models import Transaction


def tx(acc, d, amount, desc, seq=0):
    return Transaction(acc, d, D(amount), desc, seq=seq)


TODAY = date(2026, 11, 12)


def test_budget_levels():
    txs = [tx("c", date(2026, 11, 3), -90_000, "배달의민족"), tx("c", date(2026, 11, 4), -70_000, "스타벅스")]
    apply_categories(txs)
    st = {b.category: b for b in planning.budget_status(txs, {"식비": D(100_000), "카페": D(50_000), "교통": D(1)}, TODAY)}
    assert (st["식비"].level, st["카페"].level, st["교통"].level) == ("warn", "over", "ok")


def test_savings_rate():
    assert planning.savings_rate(D(4_000_000), D(3_000_000)) == D(25)
    assert planning.savings_rate(D(0), D(100)) == 0


def test_forecast_excludes_one_offs_from_pace():
    txs = [tx("c", date(2026, 11, d), -10_000, "편의점", seq=d) for d in range(1, 11)]
    big = tx("c", date(2026, 11, 5), -900_000, "가전")
    fc = planning.month_forecast(txs + [big], date(2026, 11, 10), D(50_000), {big.id})
    # 쓴 돈 100만 + 평소 하루 1만 × 남은 20일 + 고정지출 5만
    assert (fc.spent_so_far, fc.projected) == (D(1_000_000), D(1_250_000))


def test_goal_monthly_needed():
    g = planning.Goal("여행", D(3_000_000), D(1_800_000), date(2027, 2, 28))
    assert g.monthly_needed(TODAY) == D(400_000)
    assert round(g.pct) == 60


def test_recurring_found_and_irregular_ignored():
    txs = [tx("c", date(2026, m, 5), -17_000, f"넷플릭스 {m}월분") for m in range(6, 12)]
    txs += [tx("c", date(2026, m, 9), -(m * 10_000), "쿠팡") for m in range(6, 12)]  # 금액 들쭉날쭉
    found = recurring.find_recurring(txs)
    assert [(r.amount, r.day_of_month, r.months) for r in found] == [(D(17_000), 5, 6)]
    assert found[0].charged_this_month(TODAY)


def test_anomaly_new_merchant_and_outlier():
    hist = [tx("c", date(2026, 10, d), -20_000, "배달의민족", seq=d) for d in range(1, 11)]
    new = tx("c", date(2026, 11, 10), -890_000, "하이마트 온라인몰")
    spike = tx("c", date(2026, 11, 11), -200_000, "배달의민족")
    txs = hist + [new, spike]
    apply_categories(txs)
    reasons = {a.tx.description: a.reason for a in anomalies.find_anomalies(txs, TODAY)}
    assert reasons["하이마트 온라인몰"].startswith("처음 보는")
    assert "평소" in reasons["배달의민족"]


def test_card_performance():
    txs = [tx("k", date(2026, 11, 2), -120_000, "이마트"), tx("k", date(2026, 11, 3), 20_000, "이마트 취소"),
           tx("k", date(2026, 10, 3), -999_000, "지난달")]
    [c] = cards.card_performance(txs, {"k": ("KB국민카드", D(300_000))}, TODAY)
    assert (c.spent, c.remaining, c.days_left) == (D(100_000), D(200_000), 18)


def test_dividend_calendar_krw_after_tax():
    divs = [dividends.Dividend(date(2026, 5, 16), "AAPL", "Apple", D(10), "USD", D(1400), D("1.5"))]
    cal = dividends.monthly_calendar(divs, 2026)
    assert cal[5] == D(11_900) and cal[6] == 0


def test_pension_credit_limits_and_rate():
    p = yearend.pension_credit(D(45_000_000), D(7_000_000), D(4_000_000))
    assert (p.eligible, p.room_left) == (D(9_000_000), D(0))  # 연금저축 600만 + IRP 300만까지만
    assert p.credit == D(9_000_000) * D("0.165")
    assert yearend.pension_credit(D(80_000_000), D(1_000_000), D(0)).rate == D("0.132")


def test_himart_is_not_grocery():
    t = tx("c", TODAY, -1, "하이마트 온라인몰")
    apply_categories([t])
    assert t.category == "가전·가구"


def test_export_payload_has_every_section():
    payload = export.build_payload(demo.build(TODAY), TODAY)
    for key in ["kpi", "budgets", "recurring", "forecast", "anomalies", "cards", "dividends",
                "networth_history", "goals", "yearend", "invest", "transactions"]:
        assert payload[key], key
    assert payload["yearend"]["pension"]["credit"] > 0
