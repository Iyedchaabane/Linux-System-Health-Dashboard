"""Domain errors for the Linux system health dashboard."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain errors."""


class UnsupportedMetric(DomainError):
    """Raised when a requested metric is not supported."""


class PermissionDenied(DomainError):
    """Raised when a metric read is not permitted."""


class TransientFailure(DomainError):
    """Raised when a metric read transiently fails."""
