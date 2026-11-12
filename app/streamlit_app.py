"""가계부 웹 대시보드 (PC 화면용). 실행: streamlit run app/streamlit_app.py

지금은 가짜 데이터(demo)로 화면을 보여 줍니다. Supabase 연결 후 실제 데이터로 바뀝니다.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ledger import assets, demo, summary, yearend  # noqa: E402
from ledger.brokers import FakeBrokerClient  # noqa: E402
from ledger.portfolio import build_holdings, value_holdings  # noqa: E402

st.set_page_config(page_title="가계부 대시보드", page_icon="💰", layout="wide")

DAYS = ["월", "화", "수", "목", "금", "토", "일"]
ASSET_KEYS = ["현금", "국내주식", "해외주식"]


def won(x: Decimal | float) -> str:
    return f"{float(x):,.0f}원"


def bars(labels: list[str], values: list[float], name: str = "금액") -> None:
    """라벨을 가로로 눕히지 않고, 주어진 순서대로 그리는 막대그래프."""
    df = pd.DataFrame({"x": labels, name: values})
    st.altair_chart(alt.Chart(df).mark_bar().encode(
        x=alt.X("x:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y(f"{name}:Q", title=None),
        tooltip=["x", alt.Tooltip(f"{name}:Q", format=",.0f")],
    ), use_container_width=True)


def table(df: pd.DataFrame) -> None:
    st.dataframe(df, hide_index=True, use_container_width=True)


@st.cache_data
def load(today: date) -> demo.DemoData:
    return demo.build(today)


# ---------- 데이터 준비 ----------
today = date.today()
data = load(today)
txs = data.transactions

broker = FakeBrokerClient()
holdings = build_holdings(data.trades)
live = [h for h in holdings.values() if h.quantity]
quotes = broker.fetch_quotes([h.symbol for h in live])
fx = broker.fetch_fx_rates(sorted({h.currency for h in live if h.currency != "KRW"}))
vals = value_holdings(holdings, {s: q.price for s, q in quotes.items()}, fx)
ab = assets.breakdown(data.cash_balances, vals, data.card_due)

this_mon = summary.week_start(today)
last_mon = this_mon - timedelta(days=7)
this_week = summary.daily_expense(txs, this_mon, today)
last_week_same = summary.daily_expense(txs, last_mon, last_mon + (today - this_mon))
spent_week = sum(this_week.values(), Decimal(0))
spent_last = sum(last_week_same.values(), Decimal(0))
months = summary.monthly(txs)
this_month = next((m for m in months if m.label == today.strftime("%Y-%m")), None)

total_val = sum((v.value_krw for v in vals), Decimal(0))
total_unreal = sum((v.unrealized_krw for v in vals), Decimal(0))
total_real = sum((h.realized_krw for h in holdings.values()), Decimal(0))

# ---------- 사이드바 ----------
with st.sidebar:
    st.title("💰 가계부")
    page = st.radio("메뉴", ["대시보드", "지출분석", "투자분석", "자산분석", "연말정산"], label_visibility="collapsed")
    st.divider()
    st.caption(f"기준일 {today:%Y-%m-%d}")
    st.caption("⚠️ 미리보기: 가짜 데이터입니다.")

# ---------- 대시보드 ----------
if page == "대시보드":
    st.header("한눈에 보기")
    k = st.columns(5)
    k[0].metric("오늘 지출", won(this_week[today]))
    k[1].metric("이번 주 지출", won(spent_week), delta=f"{float(spent_week - spent_last):+,.0f}원 vs 지난주",
                delta_color="inverse")
    k[2].metric("이번 달 지출", won(this_month.expense if this_month else 0))
    k[3].metric("순자산", won(ab.net_worth))
    k[4].metric("투자 평가손익", won(total_unreal))

    left, right = st.columns(2)
    with left:
        st.subheader("이번 주 요일별 지출")
        bars([f"{DAYS[d.weekday()]} {d:%m/%d}" for d in this_week], [float(v) for v in this_week.values()], "지출")
    with right:
        st.subheader("최근 12주 지출 (주 시작일 기준)")
        w = summary.weekly(txs)[-12:]
        bars([r.label[5:] for r in w], [float(r.expense) for r in w], "지출")

    left, right = st.columns(2)
    with left:
        st.subheader("이번 주 카테고리")
        cat = summary.by_category(txs, this_mon, today)
        table(pd.DataFrame({"카테고리": list(cat.keys()), "금액": [won(v) for v in cat.values()]}))
    with right:
        st.subheader("자산 구성")
        shares = ab.shares()
        st.bar_chart(pd.Series({k: float(shares.get(k, 0)) for k in ASSET_KEYS}), horizontal=True)

# ---------- 지출분석 ----------
elif page == "지출분석":
    st.header("지출분석")
    period = st.radio("단위", ["주간", "월간"], horizontal=True)
    rows = summary.weekly(txs)[-12:] if period == "주간" else summary.monthly(txs)[-12:]
    st.line_chart(pd.DataFrame({"수입": [float(r.income) for r in rows], "지출": [float(r.expense) for r in rows],
                                "남은 돈": [float(r.net) for r in rows]}, index=[r.label for r in rows]))
    left, right = st.columns(2)
    with left:
        st.subheader("최근 4주 카테고리별 지출")
        cat4 = summary.by_category(txs, today - timedelta(days=27), today)
        st.bar_chart(pd.Series({k: float(v) for k, v in cat4.items()}), horizontal=True)
    with right:
        st.subheader("최근 30일 큰 지출")
        big = sorted((t for t in txs if t.counts_in_budget and t.amount < 0
                      and t.occurred_on > today - timedelta(days=30)), key=lambda t: t.amount)[:10]
        table(pd.DataFrame({"날짜": [t.occurred_on for t in big], "내용": [t.description for t in big],
                            "카테고리": [t.category for t in big], "금액": [won(-t.amount) for t in big]}))
    st.subheader("전체 거래 내역")
    q = st.text_input("검색 (가게명, 카테고리)")
    recent = [t for t in sorted(txs, key=lambda t: t.occurred_on, reverse=True)
              if not q or q in t.description or q in t.category][:300]
    table(pd.DataFrame({"날짜": [t.occurred_on for t in recent], "내용": [t.description for t in recent],
                        "카테고리": [t.category for t in recent], "금액": [won(t.amount) for t in recent],
                        "집계": ["포함" if t.counts_in_budget else "제외" for t in recent]}))

# ---------- 투자분석 ----------
elif page == "투자분석":
    st.header("투자분석")
    k = st.columns(4)
    k[0].metric("평가금액", won(total_val))
    k[1].metric("평가손익", won(total_unreal))
    k[2].metric("실현손익", won(total_real))
    k[3].metric("환율", ", ".join(f"{c} {float(r):,.0f}원" for c, r in fx.items()) or "-")
    table(pd.DataFrame({
        "종목": [v.holding.name for v in vals],
        "시장": ["국내" if v.holding.currency == "KRW" else "해외" for v in vals],
        "수량": [float(v.holding.quantity) for v in vals],
        "평단": [f"{float(v.holding.avg_price):,.2f} {v.holding.currency}" for v in vals],
        "현재가": [f"{float(v.price):,.2f} {v.holding.currency}" for v in vals],
        "평가액": [won(v.value_krw) for v in vals],
        "평가손익": [won(v.unrealized_krw) for v in vals],
        "수익률": [f"{float(v.return_pct):+.1f}%" for v in vals],
    }))
    st.subheader("종목별 평가액")
    st.bar_chart(pd.Series({v.holding.name: float(v.value_krw) for v in vals}), horizontal=True)

# ---------- 자산분석 ----------
elif page == "자산분석":
    st.header("자산분석")
    k = st.columns(3)
    k[0].metric("순자산", won(ab.net_worth))
    k[1].metric("총자산", won(ab.total))
    k[2].metric("결제 예정 카드대금", won(ab.card_due))
    shares = ab.shares()
    left, right = st.columns(2)
    with left:
        st.bar_chart(pd.Series({k: float(shares.get(k, 0)) for k in ASSET_KEYS}), horizontal=True)
    with right:
        table(pd.DataFrame({"구분": ASSET_KEYS,
                            "금액": [won(ab.cash), won(ab.domestic_stock), won(ab.foreign_stock)],
                            "비중": [f"{float(shares.get(k, 0)):.1f}%" for k in ASSET_KEYS]}))

# ---------- 연말정산 ----------
else:
    st.header("연말정산")
    st.caption("신용카드 등 소득공제 **추정치**입니다. 최종 금액은 국세청 간소화 자료로 확인하세요.")
    salary = st.number_input("올해 총급여 (세전 연봉)", min_value=0, value=45_600_000, step=1_000_000)
    rules = yearend.YearEndRules()
    spend = yearend.spend_by_group(txs, today.year, demo.CARD_PAYMENT_TYPES, rules)
    est = yearend.estimate(Decimal(salary), spend, rules)
    k = st.columns(3)
    k[0].metric("올해 카드 등 사용액", won(est.total_spend))
    k[1].metric("공제 문턱 (총급여 25%)", won(est.threshold))
    k[2].metric("예상 소득공제", won(est.deduction))
    progress = float(min(est.total_spend / est.threshold, 1)) if est.threshold else 1.0
    st.progress(progress, text=f"공제 문턱 {progress * 100:.0f}% 달성")
    st.info(est.advice)
    table(pd.DataFrame({"구분": [yearend.GROUP_LABELS[g] for g in yearend.GROUPS],
                        "사용액": [won(est.spend[g]) for g in yearend.GROUPS],
                        "공제율": [f"{float(rules.rates[g]) * 100:.0f}%" for g in yearend.GROUPS]}))
