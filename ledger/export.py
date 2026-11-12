"""계산 결과를 웹 화면용 JSON으로 내보냅니다.

    python -m ledger.export web/data.json        # 가짜 데이터로 미리보기
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from decimal import Decimal

from ledger import anomalies, assets, cards, demo, dividends, planning, recurring, summary, yearend
from ledger.brokers import FakeBrokerClient
from ledger.portfolio import build_holdings, value_holdings

DAYS = ["월", "화", "수", "목", "금", "토", "일"]


def f(x: Decimal | float | int) -> float:
    return round(float(x), 2)


def build_payload(data: demo.DemoData, today: date, broker=None) -> dict:
    broker = broker or FakeBrokerClient()
    txs = data.transactions

    # 지출
    mon = summary.week_start(today)
    last_mon = mon - timedelta(days=7)
    week = summary.daily_expense(txs, mon, mon + timedelta(days=6))
    last_week = summary.daily_expense(txs, last_mon, last_mon + timedelta(days=6))
    week_so_far = sum((v for d, v in week.items() if d <= today), Decimal(0))
    last_same = sum((v for d, v in last_week.items() if d <= last_mon + (today - mon)), Decimal(0))
    months = summary.monthly(txs)
    cur = next((m for m in months if m.label == today.strftime("%Y-%m")), summary.PeriodSummary("", Decimal(0), Decimal(0)))
    prev_label = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    prev = next((m for m in months if m.label == prev_label), None)

    recs = recurring.find_recurring(txs)
    fixed_left = sum((r.amount for r in recs if not r.charged_this_month(today)), Decimal(0))
    anoms = anomalies.find_anomalies(txs, today)
    rec_keys = {recurring.key(r.name) for r in recs}
    month_start = today.replace(day=1)
    not_usual = {t.id for t in txs if t.occurred_on >= month_start and recurring.key(t.description) in rec_keys}
    not_usual |= {a.tx.id for a in anoms}
    fc = planning.month_forecast(txs, today, fixed_left, not_usual)

    # 투자
    holdings = build_holdings(data.trades)
    live = [h for h in holdings.values() if h.quantity]
    quotes = broker.fetch_quotes([h.symbol for h in live])
    fx = broker.fetch_fx_rates(sorted({h.currency for h in live if h.currency != "KRW"}))
    vals = value_holdings(holdings, {s: q.price for s, q in quotes.items()}, fx)
    ab = assets.breakdown(data.cash_balances, vals, data.card_due)

    # 연말정산
    rules = yearend.YearEndRules()
    est = yearend.estimate(data.salary, yearend.spend_by_group(txs, today.year, demo.CARD_PAYMENT_TYPES, rules), rules)
    pen = yearend.pension_credit(data.salary, data.pension_paid, data.irp_paid)

    div_cal = dividends.monthly_calendar(data.dividends, today.year)

    return {
        "meta": {"today": today.isoformat(), "demo": True},
        "kpi": {
            "today": f(week.get(today, 0)), "week": f(week_so_far), "last_week_same": f(last_same),
            "month_expense": f(cur.expense), "month_income": f(cur.income),
            "prev_month_expense": f(prev.expense) if prev else None,
            "savings_rate": f(planning.savings_rate(prev.income, prev.expense)) if prev else None,
            "savings_month": prev_label,
            "net_worth": f(ab.net_worth),
        },
        "week_daily": [{"date": d.isoformat(), "label": f"{DAYS[d.weekday()]} {d:%m/%d}", "amount": f(v),
                        "last": f(last_week[last_mon + timedelta(days=i)]), "future": d > today}
                       for i, (d, v) in enumerate(week.items())],
        "weekly": [{"label": r.label, "income": f(r.income), "expense": f(r.expense)} for r in summary.weekly(txs)[-16:]],
        "monthly": [{"label": r.label, "income": f(r.income), "expense": f(r.expense),
                     "savings_rate": f(planning.savings_rate(r.income, r.expense))} for r in months[-12:]],
        "category_month": [{"category": k, "amount": f(v)}
                           for k, v in summary.by_category(txs, today.replace(day=1), today).items()],
        "budgets": [{"category": b.category, "budget": f(b.budget), "spent": f(b.spent), "pct": f(b.pct),
                     "level": b.level} for b in planning.budget_status(txs, data.budgets, today)],
        "forecast": {"spent": f(fc.spent_so_far), "projected": f(fc.projected), "fixed_left": f(fixed_left),
                     "days_elapsed": fc.days_elapsed, "days_in_month": fc.days_in_month,
                     "budget_total": f(sum(data.budgets.values(), Decimal(0)))},
        "recurring": [{"name": r.name, "amount": f(r.amount), "day": r.day_of_month, "months": r.months,
                       "category": r.category, "charged": r.charged_this_month(today)} for r in recs],
        "anomalies": [{"date": a.tx.occurred_on.isoformat(), "description": a.tx.description,
                       "amount": f(-a.tx.amount), "reason": a.reason} for a in anoms],
        "cards": [{"name": c.name, "required": f(c.required), "spent": f(c.spent), "remaining": f(c.remaining),
                   "pct": f(c.pct), "days_left": c.days_left}
                  for c in cards.card_performance(txs, data.card_requirements, today)],
        "transactions": [{"date": t.occurred_on.isoformat(), "description": t.description, "category": t.category,
                          "amount": f(t.amount), "included": t.counts_in_budget}
                         for t in sorted(txs, key=lambda t: t.occurred_on, reverse=True)[:500]],
        "invest": {
            "value": f(sum((v.value_krw for v in vals), Decimal(0))),
            "unrealized": f(sum((v.unrealized_krw for v in vals), Decimal(0))),
            "realized": f(sum((h.realized_krw for h in holdings.values()), Decimal(0))),
            "fx": {c: f(r) for c, r in fx.items()},
            "holdings": [{"name": v.holding.name, "market": "국내" if v.holding.currency == "KRW" else "해외",
                          "quantity": f(v.holding.quantity), "avg_price": f(v.holding.avg_price),
                          "price": f(v.price), "currency": v.holding.currency, "value": f(v.value_krw),
                          "unrealized": f(v.unrealized_krw), "return_pct": f(v.return_pct)} for v in vals],
        },
        "dividends": {
            "year": today.year,
            "calendar": [{"month": m, "amount": f(a)} for m, a in div_cal.items()],
            "by_symbol": [{"name": k, "amount": f(v)} for k, v in dividends.by_symbol(data.dividends, today.year).items()],
            "total": f(sum(div_cal.values(), Decimal(0))),
        },
        "assets": {"cash": f(ab.cash), "domestic": f(ab.domestic_stock), "foreign": f(ab.foreign_stock),
                   "card_due": f(ab.card_due), "total": f(ab.total), "net_worth": f(ab.net_worth)},
        "networth_history": [{"month": m, "value": f(v)} for m, v in data.networth_history],
        "goals": [{"name": g.name, "target": f(g.target), "saved": f(g.saved), "pct": f(g.pct),
                   "deadline": g.deadline.isoformat(), "monthly_needed": f(g.monthly_needed(today))} for g in data.goals],
        "yearend": {
            "salary": f(data.salary), "threshold": f(est.threshold), "total_spend": f(est.total_spend),
            "deduction": f(est.deduction), "remaining_to_threshold": f(est.remaining_to_threshold),
            "basic_limit": f(est.basic_limit), "advice": est.advice,
            "groups": [{"key": g, "label": yearend.GROUP_LABELS[g], "spend": f(est.spend[g]),
                        "rate": f(rules.rates[g] * 100)} for g in yearend.GROUPS],
            "pension": {"pension_paid": f(data.pension_paid), "irp_paid": f(data.irp_paid),
                        "eligible": f(pen.eligible), "credit": f(pen.credit), "room_left": f(pen.room_left),
                        "rate": f(pen.rate * 100)},
        },
    }


def main(out: str = "web/data.json") -> None:
    today = date.today()
    payload = build_payload(demo.build(today), today)
    with open(out, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=1)
    print(f"wrote {out}")


if __name__ == "__main__":
    main(*sys.argv[1:])
