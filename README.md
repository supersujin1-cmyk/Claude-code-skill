# 가계부

KB국민카드·삼성카드·국민은행·KB증권(국내+해외) 내역을 모아 PC 웹사이트에서 매일 보는 대시보드.

메뉴: 요약 · 지출 · 예산·목표 · 투자 · 자산 · 연말정산 · 거래내역

## 미리보기 (가짜 데이터)

```bash
pip install -e ".[dev]"
python -m ledger.export web/data.json
python -m http.server 8600 -d web
```

브라우저에서 http://localhost:8600 을 엽니다.

## 기능
- 요약: 오늘/이번 주/이번 달 지출, 월말 예상, 저축률, 순자산, 이상 지출 알림, 남은 고정지출
- 지출: 주간·월간 추이, 카테고리별, 월말 예상 지출, 카드 실적, 고정지출·구독 자동 탐지
- 예산·목표: 카테고리 예산 진행률, 목표 저축, 월별 저축률
- 투자: 보유 종목(국내·해외 원화 환산), 평가/실현 손익, 배당 캘린더
- 자산: 순자산 추이, 현금·국내주식·해외주식 구성
- 연말정산: 카드 소득공제 추정, 연금저축·IRP 세액공제
- 거래내역: 검색, 카테고리 필터

## 구조
- `ledger/`: 계산 로직 (표준 라이브러리만 사용)
- `ledger/export.py`: 계산 결과 → `web/data.json`
- `web/`: 대시보드 화면 (HTML + d3, 외부 CDN 없음)
- `supabase/migrations/`: DB 스키마 (본인 데이터만 보이도록 RLS)
- `.claude/plans/household-ledger.plan.md`: 진행 계획

## 보안
- 실제 금융 파일(`*.xlsx`, `*.csv`), `web/data.json`, `.streamlit/secrets.toml`은 커밋되지 않습니다.
- 저장소는 비공개로 유지하세요.
- 연말정산 값은 추정치입니다. 공제율·한도는 `ledger/yearend.py`에서 매년 확인하세요.
