"""Typed failures used across funding-arbitrage boundaries."""

from collections.abc import Mapping
from types import MappingProxyType


class FundingArbError(Exception):
    """Base class for expected project failures."""


class TransportError(FundingArbError):
    """A request failed before a usable raw response was obtained."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_text: str | None = None,
        response_headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text
        self.response_headers = MappingProxyType(dict(response_headers or {}))


class RateLimitError(TransportError):
    """The remote service explicitly rejected a request for rate limiting."""


class SchemaError(FundingArbError):
    """Raw evidence cannot be decoded as the expected source schema."""


class SemanticError(FundingArbError):
    """Source data is structurally valid but has unsupported or invalid meaning."""


class MappingError(FundingArbError):
    """Canonical identity mapping failed."""


class DataConflictError(FundingArbError):
    """Conflicting observations cannot be reconciled safely."""


class StorageError(FundingArbError):
    """A storage operation failed."""
