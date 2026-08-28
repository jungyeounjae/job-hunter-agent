import os

import httpx


GBIZ_SEARCH_URL = "https://info.gbiz.go.jp/hojin/v1/hojin"


def search_corporation(name: str) -> dict | None:
    token = os.environ.get("GBIZINFO_API_TOKEN")
    if not token:
        return None
    response = httpx.get(
        GBIZ_SEARCH_URL,
        params={"name": name, "limit": 1},
        headers={"X-hojinInfo-api-token": token},
        timeout=15.0,
    )
    if response.status_code != 200:
        return None
    payload = response.json()
    infos = payload.get("hojin-infos") or payload.get("hojin_infos") or []
    if not infos:
        return None
    return infos[0]
