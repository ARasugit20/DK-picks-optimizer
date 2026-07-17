"""Kalshi fetch tests with mocked HTTP."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from betting_system.markets.kalshi import fetch_kalshi_markets


def test_fetch_kalshi_markets_parses_response():
    """Live fetch parses Kalshi markets response."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "markets": [
            {
                "ticker": "TEST-1",
                "title": "S&P 500 above 7000 in 2026?",
                "yes_ask": 42,
                "volume": 1000000,
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_resp

    with patch("betting_system.markets.kalshi.httpx.Client", return_value=mock_client):
        rows = fetch_kalshi_markets(limit=5)
    assert len(rows) == 1
    assert rows[0]["venue"] == "kalshi"
