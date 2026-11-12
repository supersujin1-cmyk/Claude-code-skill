"""가계부 대시보드. 실행: streamlit run app/streamlit_app.py

지금은 가짜 데이터(demo)로 화면을 보여 줍니다. Supabase 연결 후 실제 데이터로 바뀝니다.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ledger import assets, demo, summary, yearend  # noqa: E402
from ledger.brokers import FakeBrokerClient  # noqa: E402
from ledger.portfolio import build_holdings, value_holdings  # noqa: E402

st.set_page_config(page_title="가계부", page_icon="💰", layout="centered")


def won(x: Decimal | float) -> str:
    return f"{float(x):,.0f}원"


@st.cache_data
def load(today: date) -> demo.DemoData:
    return demo.build(today)


today = date.today()
data = load(today)
txs = data.transactions
st.caption("⚠️ 미리보기: 가짜 데이터입니다.")

tab_week, tab_spend, tab_invest, tab_asset, tab_tax = st.tabs(
    ["이번 주", "지출분석", "투자분석", "자산분석", "연말정산"]
)

# ---------- 이번 주 ----------
with tab_week:
    this_mon = summary.week_start(today)
    last_mon = this_mon - timedelta(days=7)
    this_week = summary.daily_expense(txs, this_mon, today)
    last_week_same = summary.daily_expense(txs, last_mon, last_mon + (today - this_mon))
    spent_today = this_week[today]
    spent_week = sum(this_week.values(), Decimal(0))
    spent_last = sum(last_week_same.values(), Decimal(0))

    c1, c2 = st.columns(2)
    c1.metric("오늘 지출", won(spent_today))
    c2.metric("이번 주 지출", won(spent_week), delta=f"{float(spent_week - spent_last):+,.0f}원 (지난주 같은 기간 대비)",
              delta_color="inverse")
    days = ["월", "화", "수", "목", "금", "토", "일"]
    st.bar_chart(pd.DataFrame({"지출": [float(v) for v in this_week.values()]},
                              index=[days[d.weekday()] for d in this_week]))
    st.subheader("이번 주 카테고리")
    cat = summary.by_category(txs, this_mon, today)
    st.dataframe(pd.DataFrame({"카테고리": list(cat.keys()), "금액": [won(v) for v in cat.values()]}),
                 hide_index=True, use_container_width=True)

# ---------- 지출분석 ----------
with tab_spend:
    period = st.radio("단위", ["주간", "월간"], horizontal=True)
    rows = summary.weekly(txs)[-12:] if period == "주간" else summary.monthly(txs)[-12:]
    df = pd.DataFrame({"수입": [float(r.income) for r in rows], "지출": [float(r.expense) for r in rows]},
                      index=[r.label for r in rows])
    st.line_chart(df)
    st.subheader("최근 4주 카테고리별 지출")
    cat4 = summary.by_category(txs, today - timedelta(days=27), today)
    st.bar_chart(pd.Series({k: float(v) for k, v in cat4.items()}), horizontal=True)
    st.subheader("최근 큰 지출")
    big = sorted((t for t in txs if t.counts_in_budget and t.amount < 0
                  and t.occurred_on > today - timedelta(days=30)), key=lambda t: t.amount)[:10]
    st.dataframe(pd.DataFrame({"날짜": [t.occurred_on for t in big], "내용": [t.description for t in big],
                               "카테고리": [t.category for t in big], "금액": [won(-t.amount) for t in big]}),
                 hide_index=True, use_container_width=True)

# ---------- 투자분석 ----------
broker = FakeBrokerClient()
holdings = build_holdings(data.trades)
live = [h for h in holdings.values() if h.quantity]
quotes = broker.fetch_quotes([h.symbol for h in live])
fx = broker.fetch_fx_rates(sorted({h.currency for h in live if h.currency != "KRW"}))
vals = value_holdings(holdings, {s: q.price for s, q in quotes.items()}, fx)

with tab_invest:
    total_val = sum((v.value_krw for v in vals), Decimal(0))
    total_unreal = sum((v.unrealized_krw for v in vals), Decimal(0))
    total_real = sum((h.realized_krw for h in holdings.values()), Decimal(0))
    c1, c2, c3 = st.columns(3)
    c1.metric("평가금액", won(total_val))
    c2.metric("평가손익", won(total_unreal))
    c3.metric("실현손익", won(total_real))
    if fx:
        st.caption("환율: " + ", ".join(f"{c} {float(r):,.0f}원" for c, r in fx.items()))
    st.dataframe(pd.DataFrame({
        "종목": [v.holding.name for v in vals],
        "시장": ["국내" if v.holding.currency == "KRW" else "해외" for v in vals],
        "수량": [float(v.holding.quantity) for v in vals],
        "평단": [f"{float(v.holding.avg_price):,.2f} {v.holding.currency}" for v in vals],
        "현재가": [f"{float(v.price):,.2f} {v.holding.currency}" for v in vals],
        "평가액": [won(v.value_krw) for v in vals],
        "수익률": [f"{float(v.return_pct):+.1f}%" for v in vals],
    }), hide_index=True, use_container_width=True)

# ---------- 자산분석 ----------
with tab_asset:
    ab = assets.breakdown(data.cash_balances, vals, data.card_due)
    c1, c2 = st.columns(2)
    c1.metric("순자산", won(ab.net_worth))
    c2.metric("결제 예정 카드대금", won(ab.card_due))
    shares = ab.shares()
    st.bar_chart(pd.Series({k: float(v) for k, v in shares.items()}), horizontal=True)
    st.dataframe(pd.DataFrame({"구분": ["현금", "국내주식", "해외주식"],
                               "금액": [won(ab.cash), won(ab.domestic_stock), won(ab.foreign_stock)],
                               "비중": [f"{float(shares.get(k, 0)):.1f}%" for k in ["현금", "국내주식", "해외주식"]]}),
                 hide_index=True, use_container_width=True)

# ---------- 연말정산 ----------
with tab_tax:
    st.caption("신용카드 등 소득공제 **추정치**입니다. 최종 금액은 국세청 간소화 자료로 확인하세요.")
    salary = st.number_input("올해 총급여 (세전 연봉)", min_value=0, value=45_600_000, step=1_000_000)
    rules = yearend.YearEndRules()
    spend = yearend.spend_by_group(txs, today.year, demo.CARD_PAYMENT_TYPES, rules)
    est = yearend.estimate(Decimal(salary), spend, rules)
    c1, c2 = st.columns(2)
    c1.metric("올해 카드 등 사용액", won(est.total_spend))
    c2.metric("예상 소득공제", won(est.deduction))
    progress = float(min(est.total_spend / est.threshold, 1)) if est.threshold else 1.0
    st.progress(progress, text=f"공제 문턱(총급여 25%) {won(est.threshold)} 중 {progress * 100:.0f}%")
    st.info(est.advice)
    st.dataframe(pd.DataFrame({"구분": [yearend.GROUP_LABELS[g] for g in yearend.GROUPS],
                               "사용액": [won(est.spend[g]) for g in yearend.GROUPS],
                               "공제율": [f"{float(rules.rates[g]) * 100:.0f}%" for g in yearend.GROUPS]}),
                 hide_index=True, use_container_width=True)
