from japan_prefectures import JAPAN_PREFECTURES, match_prefecture


def test_japan_prefectures_count():
    assert len(JAPAN_PREFECTURES) == 47


def test_match_prefecture_tokyo_aliases():
    assert match_prefecture("Tokyo") == "東京都"
    assert match_prefecture("東京都") == "東京都"


def test_match_prefecture_osaka():
    assert match_prefecture("Osaka") == "大阪府"
