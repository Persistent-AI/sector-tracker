from app.services.asset_profile import _equity_metrics, _etf_metrics


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
