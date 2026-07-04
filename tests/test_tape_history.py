"""History for crypto-tape symbols that have no watchlist (YAML) entry.

Charting a tape row must synthesize a lighter crypto_perp asset; Lighter's
TradFi synthetics and unknown symbols must stay unchartable that way.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any

import pytest

from app.models import AssetConfig, Bar, GroupConfig, ProviderName, Quote
from app.providers.base import QuoteProvider
from app.providers.lighter import LighterProvider
from app.services.history import HistoryService

GROUPS = [
    GroupConfig(
        name="TEST",
        assets=[AssetConfig(symbol="AAPL", type="equity", source="yahoo")],
    )
]

TAPE_DETAILS: dict[str, dict[str, Any]] = {
    "TRX": {"symbol": "TRX", "strategy_index": 2, "status": "active", "market_id": 43},
    "MAGS": {"symbol": "MAGS", "strategy_index": 0, "status": "active", "market_id": 77},
    "AAPL": {"symbol": "AAPL", "strategy_index": 5, "status": "active", "market_id": 42},
}


def make_bar(symbol: str, provider: ProviderName, close: float, interval: str) -> Bar:
    return Bar(
        symbol=symbol,
        provider=provider,
        interval=interval,
        timestamp=datetime.now(UTC) - timedelta(minutes=5),
        open=close,
        high=close,
        low=close,
        close=close,
    )


class ScriptedHistory(QuoteProvider):
    name = "yahoo"

    def __init__(self, close: float) -> None:
        self._close = close
        self.calls: list[tuple[str, str]] = []

    async def get_quotes(self, assets: list[AssetConfig]) -> list[Quote]:
        return []

    async def get_history(self, asset: AssetConfig, *, interval: str, range_: str) -> list[Bar]:
        self.calls.append((asset.symbol, interval))
        return [make_bar(asset.symbol, "yahoo", self._close, interval)]


class ScriptedLighter(LighterProvider):
    """Real LighterProvider (isinstance matters for routing) with a warm cache."""

    def __init__(self, details: dict[str, dict[str, Any]], close: float = 0.31) -> None:
        super().__init__()
        self._details = details
        self._details_time = monotonic()
        self._close = close
        self.history_assets: list[AssetConfig] = []

    async def get_history(self, asset: AssetConfig, *, interval: str, range_: str) -> list[Bar]:
        self.history_assets.append(asset)
        return [make_bar(asset.symbol, "lighter", self._close, interval)]


def make_service(tmp_path: Path, lighter: LighterProvider | None) -> tuple[
    HistoryService, ScriptedHistory
]:
    yahoo = ScriptedHistory(close=222.0)
    providers: dict[ProviderName, QuoteProvider] = {"yahoo": yahoo}
    if lighter is not None:
        providers["lighter"] = lighter
    return HistoryService(tmp_path / "board.sqlite3", providers), yahoo


@pytest.mark.asyncio
@pytest.mark.parametrize("interval", ["1h", "1d"])
async def test_tape_symbol_charts_via_synthetic_lighter_asset(
    tmp_path: Path, interval: str
) -> None:
    lighter = ScriptedLighter(TAPE_DETAILS)
    service, yahoo = make_service(tmp_path, lighter)

    bars = await service.get_history(GROUPS, "trx", interval=interval, range_="1d")

    assert [(bar.provider, bar.close) for bar in bars] == [("lighter", 0.31)]
    assert lighter.history_assets == [
        AssetConfig(symbol="TRX", type="crypto_perp", source="lighter")
    ]
    assert yahoo.calls == []


@pytest.mark.asyncio
async def test_lighter_tradfi_market_is_not_chartable_as_tape_symbol(tmp_path: Path) -> None:
    lighter = ScriptedLighter(TAPE_DETAILS)
    service, yahoo = make_service(tmp_path, lighter)

    bars = await service.get_history(GROUPS, "MAGS", interval="1h", range_="1d")

    assert bars == []
    assert lighter.history_assets == []
    assert yahoo.calls == []


@pytest.mark.asyncio
async def test_unknown_symbol_returns_empty_without_fetch(tmp_path: Path) -> None:
    lighter = ScriptedLighter(TAPE_DETAILS)
    service, yahoo = make_service(tmp_path, lighter)

    bars = await service.get_history(GROUPS, "ZZZZ", interval="1h", range_="1d")

    assert bars == []
    assert lighter.history_assets == []
    assert yahoo.calls == []


@pytest.mark.asyncio
async def test_tape_symbol_needs_a_lighter_provider(tmp_path: Path) -> None:
    service, yahoo = make_service(tmp_path, lighter=None)

    bars = await service.get_history(GROUPS, "TRX", interval="1h", range_="1d")

    assert bars == []
    assert yahoo.calls == []


@pytest.mark.asyncio
async def test_watchlist_symbol_still_uses_its_configured_provider(tmp_path: Path) -> None:
    """AAPL is a Lighter TradFi market, but its watchlist entry must win."""
    lighter = ScriptedLighter(TAPE_DETAILS)
    service, yahoo = make_service(tmp_path, lighter)

    bars = await service.get_history(GROUPS, "AAPL", interval="1d", range_="1y")

    assert [(bar.provider, bar.close) for bar in bars] == [("yahoo", 222.0)]
    assert yahoo.calls == [("AAPL", "1d")]
    assert lighter.history_assets == []
