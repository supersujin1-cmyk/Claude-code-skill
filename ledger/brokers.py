"""증권사 연동 인터페이스.

KB증권 Open API는 신청자에게만 문서가 제공되므로, 실제 엔드포인트는 문서를 받은 뒤
`KBSecuritiesClient`에 채웁니다. 그 전까지는 `FakeBrokerClient`로 화면과 계산을 개발합니다.
조회 기능만 사용하며 주문 기능은 연결하지 않습니다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from ledger.models import Side, Trade


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: Decimal
    currency: str


class BrokerClient(Protocol):
    def fetch_trades(self, start: date, end: date) -> list[Trade]: ...
    def fetch_quotes(self, symbols: list[str]) -> dict[str, Quote]: ...
    def fetch_fx_rates(self, currencies: list[str]) -> dict[str, Decimal]: ...


class KBSecuritiesClient:
    """KB증권 Open API 클라이언트. API 문서를 받으면 구현합니다."""

    def __init__(self, app_key: str, app_secret: str, account_no: str) -> None:
        if not (app_key and app_secret and account_no):
            raise ValueError("KB증권 app_key, app_secret, account_no가 필요합니다 (secrets.toml)")
        self._app_key, self._app_secret, self._account_no = app_key, app_secret, account_no

    def fetch_trades(self, start: date, end: date) -> list[Trade]:
        raise NotImplementedError("KB증권 API 문서 수령 후 구현: 국내/해외 체결 내역 조회")

    def fetch_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        raise NotImplementedError("KB증권 API 문서 수령 후 구현: 현재가 조회")

    def fetch_fx_rates(self, currencies: list[str]) -> dict[str, Decimal]:
        raise NotImplementedError("KB증권 API 문서 수령 후 구현: 환율 조회")


class FakeBrokerClient:
    """가짜 데이터. 개발과 화면 미리보기용."""

    ACCOUNT = "demo-kb-securities"

    def fetch_trades(self, start: date, end: date) -> list[Trade]:
        d = Decimal
        trades = [
            Trade(self.ACCOUNT, date(2026, 3, 2), "005930", "삼성전자", Side.BUY, d(10), d(70000), fee=d(100)),
            Trade(self.ACCOUNT, date(2026, 6, 10), "005930", "삼성전자", Side.BUY, d(10), d(80000), fee=d(100)),
            Trade(self.ACCOUNT, date(2026, 4, 1), "AAPL", "Apple", Side.BUY, d(5), d(200), "USD", d(1350), d(1), "US"),
            Trade(self.ACCOUNT, date(2026, 9, 1), "AAPL", "Apple", Side.SELL, d(2), d(230), "USD", d(1380), d(1), "US"),
        ]
        return [t for t in trades if start <= t.traded_on <= end]

    def fetch_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        table = {"005930": Quote("005930", Decimal(78000), "KRW"), "AAPL": Quote("AAPL", Decimal(240), "USD")}
        return {s: table[s] for s in symbols if s in table}

    def fetch_fx_rates(self, currencies: list[str]) -> dict[str, Decimal]:
        return {c: Decimal(1400) for c in currencies if c == "USD"}
