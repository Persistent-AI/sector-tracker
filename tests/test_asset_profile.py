from app.models import AssetConfig
from app.services import asset_profile
from app.services.asset_profile import AssetProfileService, _equity_metrics, _etf_metrics


def test_equity_average_volume_is_not_currency_prefixed() -> None:
    metrics = _equity_metrics(
        {
            "marketCap": 1_250_000_000,
            "averageVolume": 52_800_000,
            "fiftyTwoWeekHigh": 1255.19,
            "fiftyTwoWeekLow": 103.38,
        }
    )

    by_label = {str(metric["label"]): metric["value"] for metric in metrics}

    assert by_label["Market Cap"] == "$1.25B"
    assert by_label["Avg Volume"] == "52.8M"
    assert by_label["52W Range"] == "$103.38 - $1,255"
    assert "52W High" not in by_label
    assert "52W Low" not in by_label


def test_etf_average_volume_is_not_currency_prefixed() -> None:
    metrics = _etf_metrics(
        {
            "totalAssets": 18_000_000_000,
            "averageVolume": 1_240_000,
        }
    )

    by_label = {str(metric["label"]): metric["value"] for metric in metrics}

    assert by_label["Assets"] == "$18.00B"
    assert by_label["Avg Volume"] == "1.2M"


def test_partial_profile_failures_are_not_long_cached(monkeypatch) -> None:
    calls = {"count": 0}

    class FakeTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def get_info(self) -> dict[str, object]:
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("temporary profile failure")
            return {
                "longName": "AST SpaceMobile, Inc.",
                "quoteType": "EQUITY",
                "sector": "Technology",
                "longBusinessSummary": "Builds a space-based cellular broadband network.",
                "marketCap": 1_000_000_000,
            }

    monkeypatch.setattr(asset_profile.yf, "Ticker", FakeTicker)
    service = AssetProfileService(cache_seconds=3600)
    asset = AssetConfig(symbol="ASTS", type="equity", source="yahoo", name="AST SpaceMobile")

    first = service.get_profile(asset)
    second = service.get_profile(asset)

    assert first["status"] == "partial"
    assert second["status"] == "ok"
    assert second["description"] == "Builds a space-based cellular broadband network."
    assert calls["count"] == 2


def test_expired_good_profile_is_served_when_refresh_fails(monkeypatch) -> None:
    class FailingTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def get_info(self) -> dict[str, object]:
            raise RuntimeError("rate limited")

    cached = {
        "status": "ok",
        "symbol": "TSM",
        "name": "Taiwan Semiconductor Manufacturing Company Limited",
        "asset_type": "equity",
        "source": "yahoo",
        "exchange": "NYQ",
        "sector": "Technology",
        "industry": "Semiconductors",
        "website": None,
        "description": "Cached profile",
        "metrics": [{"label": "Market Cap", "value": "$1.00T"}],
    }
    monkeypatch.setattr(asset_profile.yf, "Ticker", FailingTicker)
    service = AssetProfileService(cache_seconds=1)
    service._cache["TSM"] = (0.0, cached)
    asset = AssetConfig(symbol="TSM", type="equity", source="yahoo", name="TSM")

    profile = service.get_profile(asset)

    assert profile is cached
    assert profile["description"] == "Cached profile"
