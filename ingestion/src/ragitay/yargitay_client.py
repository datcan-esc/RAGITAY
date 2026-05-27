from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://karararama.yargitay.gov.tr"
DEFAULT_SEARCH_PATH = "/aramadetaylist"
DEFAULT_DOCUMENT_PATH = "/getDokuman"
DEFAULT_DOCUMENT_ID_PARAM = "id"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=UTF-8",
    "User-Agent": "RAGITAY Collector/0.2",
}


class RateLimitError(RuntimeError):
    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class SourceConfig:
    name: str = "yargitay"
    base_url: str = DEFAULT_BASE_URL
    search_path: str = DEFAULT_SEARCH_PATH
    document_path: str = DEFAULT_DOCUMENT_PATH
    document_id_param: str = DEFAULT_DOCUMENT_ID_PARAM

    @property
    def search_url(self) -> str:
        return f"{self.base_url.rstrip('/')}{self.search_path}"

    @property
    def document_url(self) -> str:
        return f"{self.base_url.rstrip('/')}{self.document_path}"

    def build_document_url(self, document_id: str) -> str:
        query = urlencode({self.document_id_param: document_id})
        return f"{self.document_url}?{query}"


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
    def __init__(
        self,
        source_config: SourceConfig | None = None,
        timeout: float = 30.0,
        max_retries: int = 4,
        retry_backoff_seconds: float = 5.0,
    ) -> None:
        self.source_config = source_config or SourceConfig()
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    def search(self, filters: SearchFilters, page_number: int) -> dict[str, Any]:
        payload = self._post_json(self.source_config.search_url, filters.to_payload(page_number))
        self._assert_success(payload)
        return payload

    def get_document(self, document_id: str) -> dict[str, Any]:
        payload = self._get_json(self.source_config.build_document_url(document_id))
        self._assert_success(payload)
        return payload

    @staticmethod
    def _assert_success(payload: dict[str, Any]) -> None:
        metadata = payload.get("metadata", {})
        if metadata.get("FMTY") != "SUCCESS":
            raise RuntimeError(metadata.get("FMTE") or "Bilinmeyen API hatası")

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(
            Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=DEFAULT_HEADERS,
                method="POST",
            )
        )

    def _get_json(self, url: str) -> dict[str, Any]:
        return self._request_json(Request(url, headers=DEFAULT_HEADERS, method="GET"))

    def _request_json(self, request: Request) -> dict[str, Any]:
        attempt = 0

        while True:
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                if exc.code == 429 and attempt >= self.max_retries:
                    retry_after = self._parse_retry_after(exc)
                    raise RateLimitError("HTTP 429: Too Many Requests", retry_after_seconds=retry_after) from exc
                if exc.code not in {429, 500, 502, 503, 504} or attempt >= self.max_retries:
                    raise
                self._sleep_before_retry(attempt, exc.code, self._parse_retry_after(exc))
                attempt += 1
            except URLError:
                if attempt >= self.max_retries:
                    raise
                self._sleep_before_retry(attempt, "network", None)
                attempt += 1

    def _sleep_before_retry(self, attempt: int, reason: object, retry_after_seconds: float | None) -> None:
        delay = retry_after_seconds if retry_after_seconds is not None else self.retry_backoff_seconds * (2 ** attempt)
        print(f"Gecici hata ({reason}), {delay:.1f}s sonra tekrar denenecek.")
        time.sleep(delay)

    @staticmethod
    def _parse_retry_after(exc: HTTPError) -> float | None:
        value = exc.headers.get("Retry-After")
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None
