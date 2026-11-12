# 가계부

KB국민카드·삼성카드·국민은행·KB증권(국내+해외) 내역을 모아 PC 웹사이트에서 매일 보는 대시보드.

메뉴: 대시보드 · 지출분석 · 투자분석 · 자산분석 · 연말정산

## 실행 (지금은 가짜 데이터)

```bash
pip install -e ".[dev]"
streamlit run app/streamlit_app.py
pytest
```

## 구조
- `ledger/`: 계산 로직 (분류, 카드대금·이체 제외, 주간/월간 요약, 투자 손익, 자산, 연말정산)
- `app/streamlit_app.py`: 화면
- `supabase/migrations/`: DB 스키마 (본인 데이터만 보이도록 RLS)
- `.claude/plans/household-ledger.plan.md`: 진행 계획

## 보안
- 실제 금융 파일(`*.xlsx`, `*.csv`)과 `.streamlit/secrets.toml`은 커밋되지 않습니다.
- 저장소는 비공개로 유지하세요.
- 연말정산 값은 추정치입니다. 공제율·한도는 `ledger/yearend.py`의 `YearEndRules`에서 매년 확인하세요.
