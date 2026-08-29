"""日本47都道府県 — 求人検索の勤務地選択用。"""

from __future__ import annotations

JAPAN_PREFECTURES: list[str] = [
    "北海道",
    "青森県",
    "岩手県",
    "宮城県",
    "秋田県",
    "山形県",
    "福島県",
    "茨城県",
    "栃木県",
    "群馬県",
    "埼玉県",
    "千葉県",
    "東京都",
    "神奈川県",
    "新潟県",
    "富山県",
    "石川県",
    "福井県",
    "山梨県",
    "長野県",
    "岐阜県",
    "静岡県",
    "愛知県",
    "三重県",
    "滋賀県",
    "京都府",
    "大阪府",
    "兵庫県",
    "奈良県",
    "和歌山県",
    "鳥取県",
    "島根県",
    "岡山県",
    "広島県",
    "山口県",
    "徳島県",
    "香川県",
    "愛媛県",
    "高知県",
    "福岡県",
    "佐賀県",
    "長崎県",
    "熊本県",
    "大分県",
    "宮崎県",
    "鹿児島県",
    "沖縄県",
]

# 英語・略称 → 都道府県名
_PREFecture_ALIASES: dict[str, str] = {
    "japan": "東京都",
    "tokyo": "東京都",
    "東京都": "東京都",
    "tokyo-to": "東京都",
    "osaka": "大阪府",
    "大阪": "大阪府",
    "kyoto": "京都府",
    "kyoto prefecture": "京都府",
    "kanagawa": "神奈川県",
    "aichi": "愛知県",
    "nagoya": "愛知県",
    "fukuoka": "福岡県",
    "hokkaido": "北海道",
    "okinawa": "沖縄県",
}


def match_prefecture(*candidates: str | None) -> str | None:
    """プロフィールの preferred_locations 等から都道府県を推定。"""
    for raw in candidates:
        if not raw:
            continue
        text = raw.strip()
        if text in JAPAN_PREFECTURES:
            return text
        key = text.lower()
        if key in _PREFecture_ALIASES:
            return _PREFecture_ALIASES[key]
        for pref in JAPAN_PREFECTURES:
            if pref.startswith(text) or text in pref:
                return pref
    return None
