"""Errors raised by the CommissionSight client."""

from __future__ import annotations

from typing import Any, Optional


class ApiError(Exception):
    """Raised for any non-2xx API response.

    Carries the HTTP ``status`` and the parsed `RFC 9457 <https://www.rfc-editor.org/rfc/rfc9457>`_
    ``problem+json`` ``body`` when present. ``message`` is the problem ``title`` if available,
    otherwise the HTTP status line.
    """

    def __init__(self, status: int, message: str, body: Optional[Any] = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"ApiError(status={self.status!r}, message={str(self)!r})"
