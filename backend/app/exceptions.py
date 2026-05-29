from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AppError(Exception):
    message: str
    code: str
    status_code: int = 400


class SearchError(AppError):
    def __init__(self, message: str, code: str = "search_error", status_code: int = 400) -> None:
        super().__init__(message=message, code=code, status_code=status_code)
