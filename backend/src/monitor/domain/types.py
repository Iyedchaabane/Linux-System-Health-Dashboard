"""Core metric result contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeAlias, TypeVar

T = TypeVar("T")


class UnavailableKind(StrEnum):
    """Reason why a metric result is unavailable."""

    UNSUPPORTED = "unsupported"
    PERMISSION = "permission"
    TRANSIENT = "transient"
    DISABLED = "disabled"


@dataclass(frozen=True)
class Ok(Generic[T]):
    """A metric value; ``partial`` marks an incomplete grouped result."""

    value: T
    partial: bool = False


@dataclass(frozen=True)
class Unavailable:
    """No metric value is available."""

    kind: UnavailableKind
    reason: str


MetricResult: TypeAlias = Ok[T] | Unavailable
