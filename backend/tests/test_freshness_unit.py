from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_service
import events_service
import stock_service


def test_news_is_deduplicated_and_sorted_newest_first():
    items = [
        {"title": "Older result", "publishedAt": "Fri, 19 Jun 2026 09:00:00 GMT"},
        {"title": "Newest result", "publishedAt": "2026-06-20T12:00:00+00:00"},
        {"title": "Newest result", "publishedAt": "2026-06-20T11:00:00+00:00"},
    ]

    result = stock_service._finalize_news(items)

    assert [item["title"] for item in result] == ["Newest result", "Older result"]
    assert all(item["publishedAt"].endswith("+00:00") for item in result)


def test_news_headline_relevance_uses_whole_terms():
    assert stock_service._is_relevant_headline(
        "Infosys shares fall after Accenture outlook", ["INFY", "Infosys"]
    )
    assert not stock_service._is_relevant_headline(
        "Turtlemint investors plan an IPO", ["INFY", "Infosys"]
    )


def test_past_dated_catalysts_are_removed():
    catalysts = [
        "Board meeting on April 9, 2026",
        "Earnings release on July 9, 2026",
        "Potential Fed easing, conditional and undated",
    ]

    result = ai_service._remove_past_catalysts(catalysts, date(2026, 6, 20))

    assert catalysts[0] not in result
    assert result == catalysts[1:]


def test_events_only_include_explicit_non_past_dates(monkeypatch):
    class FakeTicker:
        calendar = {
            "Earnings Date": [date(2026, 4, 9), date(2026, 7, 9)],
        }

    monkeypatch.setattr(events_service.yf, "Ticker", lambda _symbol: FakeTicker())
    monkeypatch.setattr(events_service, "get_nse_announcements", lambda _symbol: [
        {"subject": "Intimation of board meeting", "date": "2026-06-01"},
        {"subject": "Board meeting on 30 June 2026", "date": "2026-06-01"},
    ])

    result = events_service.get_events("TEST", today=date(2026, 6, 20))

    assert [event["date"] for event in result] == ["2026-06-30", "2026-07-09"]
    assert all(event["date"] >= "2026-06-20" for event in result)
