from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://karararama.yargitay.gov.tr"
SEARCH_URL = f"{BASE_URL}/aramadetaylist"
DOCUMENT_URL = f"{BASE_URL}/getDokuman"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=UTF-8",
    "User-Agent": "RAGITAY Collector/0.2",
}


@dataclass
class SearchFilters:
    query: str
    page_size: int = 100
    decision_year: str = ""
    start_date: str = ""
    end_date: str = ""
    esas_year: str = ""
    esas_first_number: str = ""
    esas_last_number: str = ""
    karar_first_number: str = ""
    karar_last_number: str = ""
    ceza_chamber: str = ""
    hukuk_chamber: str = ""
    kurul_chamber: str = ""
    yargitay_mah: str = ""
    sort_field: str = "1"
    sort_direction: str = "desc"

    def to_payload(self, page_number: int) -> dict[str, dict[str, Any]]:
        return {
            "data": {
                "arananKelime": self.query,
                "esasYil": self.esas_year,
                "esasIlkSiraNo": self.esas_first_number,
                "esasSonSiraNo": self.esas_last_number,
                "kararYil": self.decision_year,
                "kararIlkSiraNo": self.karar_first_number,
                "kararSonSiraNo": self.karar_last_number,
                "baslangicTarihi": self.start_date,
                "bitisTarihi": self.end_date,
                "birimYrgCezaDaire": self.ceza_chamber,
                "birimYrgHukukDaire": self.hukuk_chamber,
                "birimYrgKurulDaire": self.kurul_chamber,
                "pageNumber": page_number,
                "pageSize": self.page_size,
                "siralama": self.sort_field,
                "siralamaDirection": self.sort_direction,
                "yargitayMah": self.yargitay_mah,
            }
        }


class YargitayClient:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def search(self, filters: SearchFilters, page_number: int) -> dict[str, Any]:
        payload = self._post_json(SEARCH_URL, filters.to_payload(page_number))
        self._assert_success(payload)
        return payload

    def get_document(self, document_id: str) -> dict[str, Any]:
        query = urlencode({"id": document_id})
        payload = self._get_json(f"{DOCUMENT_URL}?{query}")
        self._assert_success(payload)
        return payload

    @staticmethod
    def _assert_success(payload: dict[str, Any]) -> None:
        metadata = payload.get("metadata", {})
        if metadata.get("FMTY") != "SUCCESS":
            raise RuntimeError(metadata.get("FMTE") or "Bilinmeyen API hatası")

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=DEFAULT_HEADERS,
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _get_json(self, url: str) -> dict[str, Any]:
        request = Request(url, headers=DEFAULT_HEADERS, method="GET")
        with urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))
