"""Snapshot size budget enforcement shared by the WebSocket and REST layers."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Mapping
from threading import Lock
from typing import Any

from monitor.config.settings import Settings
from monitor.domain.types import UnavailableKind

logger = logging.getLogger(__name__)

# Compatibility default for direct construction (for example in tests); the
# running application always passes ``settings.snapshot_size_budget_bytes``.
DEFAULT_SNAPSHOT_BUDGET_BYTES: int = Settings.model_fields["snapshot_size_budget_bytes"].default

DEGRADED_REASON = "snapshot exceeds the configured size budget"
_terminal_warning_lock = Lock()
_last_terminal_warning: float | None = None


class SnapshotBudgetExceeded(Exception):
    """A snapshot cannot fit; retain only safe numeric diagnostics."""

    def __init__(self, budget_bytes: int, final_size_bytes: int) -> None:
        super().__init__("Snapshot exceeds size budget")
        self.budget_bytes = budget_bytes
        self.final_size_bytes = final_size_bytes


def enforce_snapshot_budget(final_size_bytes: int, budget_bytes: int) -> None:
    """Fail closed, sharing a process-wide monotonic terminal warning throttle."""
    if final_size_bytes <= budget_bytes:
        return
    global _last_terminal_warning
    with _terminal_warning_lock:
        now = time.monotonic()
        warn = _last_terminal_warning is None or now - _last_terminal_warning >= 60.0
        if warn:
            _last_terminal_warning = now
    if warn:
        logger.warning(
            "snapshot budget exceeded: budget=%d size=%d", budget_bytes, final_size_bytes
        )
    raise SnapshotBudgetExceeded(budget_bytes, final_size_bytes)


def compact_json(payload: Any) -> str:
    """Encode JSON as compact text without ASCII escaping."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _is_unavailable(group: Any) -> bool:
    """Return whether a group already reports the unavailable state."""
    return isinstance(group, Mapping) and group.get("status") == "unavailable"


def _encoded_size(payload: Any) -> int:
    """Return the UTF-8 byte length of the compact encoding of ``payload``."""
    return len(compact_json(payload).encode("utf-8"))


def fit_snapshot_to_budget(
    groups: dict[str, Any],
    encode: Callable[[dict[str, Any]], str],
    budget_bytes: int,
) -> str:
    """Return encoded snapshot text, degrading whole groups until it fits.

    ``groups`` is mutated in place. Groups are replaced, in descending encoded
    contribution order (ties by group name), with a static ``unavailable`` state
    and the message is re-encoded after each replacement. At most one pass over
    the groups is performed. If the final message still does not fit, raise
    ``SnapshotBudgetExceeded`` rather than returning oversized text.
    """
    text = encode(groups)
    if len(text.encode("utf-8")) <= budget_bytes:
        return text

    candidates = sorted(
        (name for name, group in groups.items() if not _is_unavailable(group)),
        key=lambda name: (-_encoded_size(groups[name]), name),
    )
    degraded: list[str] = []
    for name in candidates:
        groups[name] = {
            "status": "unavailable",
            "kind": UnavailableKind.TRANSIENT.value,
            "reason": DEGRADED_REASON,
        }
        degraded.append(name)
        text = encode(groups)
        if len(text.encode("utf-8")) <= budget_bytes:
            break

    enforce_snapshot_budget(len(text.encode("utf-8")), budget_bytes)
    logger.warning(
        "snapshot exceeds size budget: budget=%d size=%d degraded=%s",
        budget_bytes,
        len(text.encode("utf-8")),
        degraded,
    )
    return text
