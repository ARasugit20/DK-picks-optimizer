"""Polymarket fetch tests with mocked HTTP."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from betting_system.markets.polymarket import fetch_polymarket_markets


def test_fetch_polymarket_markets_parses_response():
    """Live fetch parses Gamma API list response."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = [
        {
            "id": "1",
            "question": "Will BTC hit $150k?",
            "outcomePrices": "[\"0.31\", \"0.69\"]",
            "volumeNum": 5000000,
        }
    ]
    mock_resp.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_resp

    with patch("betting_system.markets.polymarket.httpx.Client", return_value=mock_client):
        rows = fetch_polymarket_markets(limit=5)
    assert len(rows) == 1
    assert rows[0]["venue"] == "polymarket"
