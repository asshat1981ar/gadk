from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CapabilityRequest:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityResult:
    status: str
    payload: dict[str, Any] | None
    error: str | None
    source_backend: str
    retryable: bool

    @classmethod
    def ok(cls, payload: dict[str, Any], source_backend: str) -> "CapabilityResult":
        return cls(
            status="success",
            payload=payload,
            error=None,
            source_backend=source_backend,
            retryable=False,
        )

    @classmethod
    def _error_result(
        cls,
        error: str,
        source_backend: str,
        retryable: bool = False,
    ) -> "CapabilityResult":
        return cls(
            status="error",
            payload=None,
            error=error,
            source_backend=source_backend,
            retryable=retryable,
        )


CapabilityHandler = Callable[
    [CapabilityRequest],
    CapabilityResult | Awaitable[CapabilityResult] | dict[str, Any] | Awaitable[dict[str, Any]],
]

# Dataclasses cannot define a classmethod with the same name as a field, so keep
# the public constructor alias after class creation.
CapabilityResult.error = CapabilityResult._error_result
