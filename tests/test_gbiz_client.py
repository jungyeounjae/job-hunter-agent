from unittest.mock import patch

from gbiz_client import search_corporation


@patch("gbiz_client.httpx.get")
def test_search_corporation_parses_first_hit(mock_get, monkeypatch):
    monkeypatch.setenv("GBIZINFO_API_TOKEN", "test-token")
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "hojin-infos": [
            {"corporate_number": "1234567890123", "name": "Example KK", "location": "Tokyo"}
        ]
    }
    result = search_corporation("Example KK")
    assert result["corporate_number"] == "1234567890123"
