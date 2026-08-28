from unittest.mock import patch

from company_factcheck import build_factcheck


@patch("company_factcheck.generate_korean_text", return_value="공공 데이터상 정상 법인")
@patch("company_factcheck.search_corporation")
def test_build_factcheck_verified(mock_search, _mock_openai):
    mock_search.return_value = {
        "corporate_number": "1234567890123",
        "name": "Example KK",
        "location": "Tokyo",
    }
    fc = build_factcheck("Example KK", "https://example.com/job")
    assert fc.status == "verified"
    assert fc.corporate_number == "1234567890123"
    assert "공공" in fc.summary_ko


@patch("company_factcheck.generate_korean_text", return_value="공공 DB 미확인")
@patch("company_factcheck.search_corporation", return_value=None)
def test_build_factcheck_unconfirmed(_mock_search, _mock_openai):
    fc = build_factcheck("Unknown Co", "https://example.com/job")
    assert fc.status == "public_unconfirmed"
