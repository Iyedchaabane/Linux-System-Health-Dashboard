"""Isolated POC for resolving a host desktop entry to a contained PNG icon.

This module is a *test support* proof of concept only. It performs no shell
execution, reads no environment variables, and never raises to callers: any
uncertainty collapses to the neutral fallback.

The resolver restricts icons to PNG files located inside an explicitly
allowlisted root, verified by extension, bounded size and a standard-library
PNG/IHDR header check. Only the 8-byte PNG signature and the IHDR header are
inspected; image data is neither decoded nor rendered. Directory discovery is
bounded.

Known limitation (TOCTOU): containment and symlink checks are done by path, and
the file is opened afterwards (check-then-open). A local attacker able to swap a
path component between the check and the ``open`` call can still win that race.
This POC intentionally does not use ``openat``/``O_NOFOLLOW`` or directory file
descriptors, so the guarantee is best-effort and not race-free.
"""

from __future__ import annotations

import configparser
import os
import stat
import struct
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

MAX_ICON_BYTES = 64 * 1024  # 64 KiB
MAX_ICON_WIDTH = 256
MAX_ICON_HEIGHT = 256
MAX_ICON_PIXELS = 65536
MAX_DIRECTORY_DEPTH = 4
MAX_DIRECTORY_ENTRIES = 256
MAX_DESKTOP_CANDIDATES = 64
MAX_DESKTOP_BYTES = 64 * 1024  # 64 KiB

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_VALID_COLOR_TYPES: dict[int, set[int]] = {
    0: {1, 2, 4, 8, 16},  # greyscale
    2: {8, 16},  # truecolour
    3: {1, 2, 4, 8},  # palette
    4: {8, 16},  # greyscale + alpha
    6: {8, 16},  # truecolour + alpha
}


class _IncompleteDiscovery(Exception):
    """Discovery could not be completed safely; resolution must fail closed."""


@dataclass(frozen=True)
class IconMatch:
    """Resolution result; neutral means 'do not use an icon'."""

    source: str = "neutral"
    icon_path: Path | None = None


@dataclass(frozen=True)
class AllowedRoot:
    """An allowlisted root whose path is normalized via ``Path.resolve``."""

    path: Path
    _raw_path: Path = field(default=None, init=False, repr=False, compare=False)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        original = Path(self.path)
        object.__setattr__(self, "_raw_path", original)
        object.__setattr__(self, "path", original.resolve(strict=False))

    @classmethod
    def sentinel(cls, root: str | Path) -> AllowedRoot:
        return cls(path=root)


@dataclass
class _Budget:
    entries: int = 0
    candidates: int = 0
    exhausted: bool = False


def _has_parent_component(path: Path) -> bool:
    """Return True when any component is ``..`` (checked before any FS access)."""
    return any(part == ".." for part in Path(path).parts)


def _lexically_within(target: Path, base: Path) -> bool:
    try:
        target.relative_to(base)
    except ValueError:
        return False
    return True


def _symlink_between(path: Path, stop: Path) -> bool:
    """Check components from below ``stop`` toward ``path`` for symlinks.

    ``stop`` is exclusive: it is never probed, so callers never inspect anything
    above the approved root.
    """
    path = Path(path)
    stop = Path(stop)
    if (
        _has_parent_component(path)
        or _has_parent_component(stop)
        or not _lexically_within(path, stop)
    ):
        return True
    cursor = stop
    for component in path.relative_to(stop).parts:
        cursor = cursor / component
        try:
            if cursor.is_symlink():
                return True
        except OSError as exc:
            raise _IncompleteDiscovery from exc
    return False


def _norm(value: object) -> str:
    return str(value).strip().lower()


def _basename(value: object) -> str:
    return Path(str(value).strip().strip('"').strip("'")).name.lower()


def _first_token(command: str) -> str:
    text = command.strip()
    if not text:
        return ""
    parts = text.split()
    token = parts[0].strip().strip('"').strip("'")
    return token


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_roots(roots: Iterable[object]) -> list[AllowedRoot]:
    result: list[AllowedRoot] = []
    for root in roots:
        if isinstance(root, AllowedRoot):
            result.append(root)
        else:
            result.append(AllowedRoot(root))
    return result


def _raw_root(root: AllowedRoot) -> Path:
    return getattr(root, "_raw_path", root.path)


def _is_within_root(candidate: object, root: AllowedRoot) -> bool:
    """Lexical-first containment; filesystem checks only after validation.

    Lexical rejections and confirmed symlinks return ``False``. A filesystem
    probe that fails raises ``_IncompleteDiscovery``: containment cannot be
    established, so callers must fail closed instead of treating it as "outside".
    """
    try:
        raw_root = _raw_root(root)
        candidate_path = Path(candidate)
        if _has_parent_component(raw_root) or _has_parent_component(candidate_path):
            return False
        if candidate_path.is_absolute():
            target = candidate_path
            bases = (raw_root, root.path)
        else:
            anchor = raw_root if raw_root.is_absolute() else root.path
            target = anchor / candidate_path
            bases = (anchor,)
        base = next((item for item in bases if _lexically_within(target, item)), None)
        if base is None:
            return False
        if _symlink_between(target, base):
            return False
        target.resolve(strict=False).relative_to(root.path)
        return True  # noqa: TRY300
    except ValueError:
        return False
    except (OSError, RuntimeError) as exc:
        raise _IncompleteDiscovery from exc


def _scan_root(root: AllowedRoot, budget: _Budget) -> list[Path]:
    results: list[Path] = []
    if budget.exhausted:
        return results

    def visit(directory: Path, depth: int) -> None:
        nonlocal results
        if budget.exhausted:
            return
        if depth > MAX_DIRECTORY_DEPTH:
            budget.exhausted = True
            return
        if not _is_within_root(directory, root):
            return
        remaining = MAX_DIRECTORY_ENTRIES - budget.entries
        names: list[str] = []
        try:
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    if len(names) >= remaining:
                        budget.exhausted = True
                        return
                    names.append(entry.name)
        except (OSError, ValueError, RuntimeError):
            budget.exhausted = True
            return
        names.sort()
        budget.entries += len(names)
        for name in names:
            if budget.exhausted:
                return
            child = directory / name
            try:
                if not _is_within_root(child, root):
                    continue
                try:
                    mode = child.lstat().st_mode
                except OSError as exc:
                    raise _IncompleteDiscovery from exc
                if stat.S_ISDIR(mode):
                    if depth + 1 > MAX_DIRECTORY_DEPTH:
                        budget.exhausted = True
                    else:
                        visit(child, depth + 1)
                elif stat.S_ISREG(mode) and Path(name).suffix.lower() == ".desktop":
                    if budget.candidates >= MAX_DESKTOP_CANDIDATES:
                        budget.exhausted = True
                        return
                    budget.candidates += 1
                    results.append(child)
                # Symlinks and other non-regular children are a normal rejection.
            except (OSError, ValueError, RuntimeError):
                continue

    try:
        if not _is_within_root(root.path, root):
            return results
        visit(root.path, 0)
    except _IncompleteDiscovery:
        budget.exhausted = True
        return []
    except (OSError, ValueError, RuntimeError):
        return []
    return results


def _desktop_entries(
    roots: list[AllowedRoot], explicit: Iterable[object] | None
) -> tuple[list[Path], bool]:
    budget = _Budget()
    if not roots:
        return [], False
    if explicit is not None:
        processed: list[Path] = []
        for item in explicit:
            if budget.candidates >= MAX_DESKTOP_CANDIDATES:
                budget.exhausted = True
                break
            budget.candidates += 1
            try:
                path = Path(str(item))
            except (TypeError, ValueError):
                continue
            if not path.is_absolute():
                interpretations = {root.path / path for root in roots}
                if len(interpretations) != 1:
                    continue
                path = interpretations.pop()
            if not any(_is_within_root(path, root) for root in roots):
                continue
            processed.append(path)
        return processed, budget.exhausted
    found: list[Path] = []
    for root in roots:
        found.extend(_scan_root(root, budget))
        if budget.exhausted:
            found.clear()
            break
    return found, budget.exhausted


def _read_desktop(path: Path, root: AllowedRoot) -> dict[str, str] | None:
    """Parse a .desktop file.

    Returns ``None`` only for genuinely malformed content. Raises
    ``_IncompleteDiscovery`` when the file cannot be read safely (permission
    errors, races or a file larger than ``MAX_DESKTOP_BYTES``).
    """
    if path.is_symlink():
        return None
    if not _is_within_root(path, root):
        return None
    try:
        stat_result = path.stat()
    except OSError as exc:
        raise _IncompleteDiscovery from exc
    if not stat.S_ISREG(stat_result.st_mode):
        return None
    if stat_result.st_size > MAX_DESKTOP_BYTES:
        raise _IncompleteDiscovery("desktop file too large")
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            text = handle.read(MAX_DESKTOP_BYTES + 1)
    except OSError as exc:
        raise _IncompleteDiscovery from exc
    if len(text) > MAX_DESKTOP_BYTES:
        raise _IncompleteDiscovery("desktop file too large")

    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.optionxform = str  # type: ignore[assignment]
    try:
        parser.read_string(text)
    except configparser.Error:
        return None
    section = "Desktop Entry"
    if not parser.has_section(section):
        section = parser.default_section
    keys = ("Name", "Exec", "TryExec", "Icon", "Type", "DBusActivatable")
    result: dict[str, str] = {}
    for key in keys:
        try:
            result[key] = parser.get(section, key, fallback="").strip()
        except (configparser.Error, KeyError, ValueError):
            result[key] = ""
    return result


def _valid_png_file(icon: Path, roots: list[AllowedRoot]) -> bool:
    if not roots:
        return False
    if not any(_is_within_root(icon, root) for root in roots):
        return False
    if icon.suffix.lower() != ".png":
        return False
    if icon.is_symlink():
        return False
    try:
        if not icon.is_file():
            return False
        size = icon.stat().st_size
    except OSError:
        return False
    if not (0 < size <= MAX_ICON_BYTES):
        return False
    try:
        with icon.open("rb") as handle:
            signature = handle.read(8)
            if signature != _PNG_SIGNATURE:
                return False
            length_bytes = handle.read(4)
            type_bytes = handle.read(4)
            if len(length_bytes) != 4 or len(type_bytes) != 4:
                return False
            (length,) = struct.unpack(">I", length_bytes)
            if length != 13:
                return False
            if type_bytes != b"IHDR":
                return False
            ihdr = handle.read(13)
            if len(ihdr) != 13:
                return False
            width, height, bit_depth, color_type, compression, filt, interlace = struct.unpack(
                ">IIBBBBB", ihdr
            )
            if width < 1 or height < 1:
                return False
            if width > MAX_ICON_WIDTH or height > MAX_ICON_HEIGHT:
                return False
            if width * height > MAX_ICON_PIXELS:
                return False
            allowed_depths = _VALID_COLOR_TYPES.get(color_type)
            if allowed_depths is None or bit_depth not in allowed_depths:
                return False
            if compression != 0 or filt != 0:
                return False
            return interlace in (0, 1)
    except (OSError, struct.error, ValueError, EOFError, RuntimeError):
        return False


def _normalize_executable(executable: str | None) -> str | None:
    if executable is None:
        return None
    token = _first_token(str(executable)) if " " in str(executable) else str(executable)
    if not token:
        return None
    return _basename(token)


def _matches_identity(
    entry: dict[str, str],
    entry_path: Path,
    *,
    query: str | None,
    executable: str | None,
    desktop: str | None,
    icon_path: str | None,
) -> bool:
    identities: list[str] = []
    if query is not None and str(query).strip():
        query_norm = _basename(query)
        identities.append(query_norm)
    if executable is not None and str(executable).strip():
        ex = _normalize_executable(executable)
        if ex:
            identities.append(ex)
    if desktop is not None and str(desktop).strip():
        identities.append(_basename(desktop))
    if icon_path is not None and str(icon_path).strip():
        identities.append(_basename(icon_path))

    if not identities:
        return False

    entry_exec = _first_token(entry.get("Exec", ""))
    desktop_basename = entry_path.name.lower()
    icon_value = entry.get("Icon", "")
    icon_basename = _basename(icon_value) if icon_value else ""

    candidate_identities = set()
    if entry_exec:
        candidate_identities.add(_basename(entry_exec))
    candidate_identities.add(desktop_basename)
    if icon_basename:
        candidate_identities.add(icon_basename)

    return any(ident and ident in candidate_identities for ident in identities)


def resolve_host_icon(
    roots: Iterable[object] = (),
    *,
    query: object = None,
    executable: object = None,
    desktop: object = None,
    icon_path: object = None,
    desktop_files: Iterable[object] | None = None,
    **_ignored: object,
) -> IconMatch:
    """Resolve a host desktop entry to a contained PNG icon path.

    Never raises; returns a neutral match on any uncertainty.
    """
    try:
        root_list = _to_roots(roots)
        if not root_list:
            return IconMatch(source="neutral", icon_path=None)
        entries, exhausted = _desktop_entries(root_list, desktop_files)
        if exhausted:
            return IconMatch(source="neutral", icon_path=None)

        matches: list[tuple[Path, dict[str, str]]] = []
        for entry_path in entries:
            try:
                entry_root = next(
                    (root for root in root_list if _is_within_root(entry_path, root)),
                    None,
                )
                if entry_root is None:
                    continue
                meta = _read_desktop(entry_path, entry_root)
                if meta is None:
                    continue
                entry_type = meta.get("Type", "").strip()
                if entry_type not in ("", "Application"):
                    continue
                if meta.get("TryExec", "").strip():
                    try_path = Path(meta["TryExec"].strip().strip('"').strip("'"))
                    if not try_path.is_absolute():
                        # Relative TryExec is not resolvable against PATH here;
                        # treat the entry as unverifiable.
                        continue
                    if not any(_is_within_root(try_path, root) for root in root_list):
                        continue
                    if not try_path.exists():
                        continue
                if (
                    not _truthy(meta.get("DBusActivatable", ""))
                    and not meta.get("Exec", "").strip()
                ):
                    continue
                if not _matches_identity(
                    meta,
                    entry_path,
                    query=(None if query is None else str(query)),
                    executable=(None if executable is None else str(executable)),
                    desktop=(None if desktop is None else str(desktop)),
                    icon_path=(None if icon_path is None else str(icon_path)),
                ):
                    continue
                matches.append((entry_path, meta))
            except (OSError, ValueError, RuntimeError):
                continue

        if len(matches) != 1:
            return IconMatch(source="neutral", icon_path=None)

        entry_path, meta = matches[0]
        icon_value = meta.get("Icon", "").strip()
        if not icon_value:
            if _truthy(meta.get("DBusActivatable", "")):
                pass
            else:
                return IconMatch(source="neutral", icon_path=None)

        if not icon_value:
            return IconMatch(source="neutral", icon_path=None)

        if Path(icon_value).is_absolute():
            icon_candidates = [Path(icon_value)]
        else:
            icon_candidates = [entry_path.parent / icon_value]

        valid_paths: list[Path] = []
        for candidate in icon_candidates:
            try:
                if not any(_is_within_root(candidate, root) for root in root_list):
                    continue
                if not _valid_png_file(candidate, root_list):
                    continue
                valid_paths.append(candidate)
            except (OSError, ValueError, RuntimeError):
                continue

        if len(valid_paths) != 1:
            return IconMatch(source="neutral", icon_path=None)

        return IconMatch(source="desktop", icon_path=valid_paths[0])
    except _IncompleteDiscovery:
        return IconMatch(source="neutral", icon_path=None)
    except Exception:
        return IconMatch(source="neutral", icon_path=None)


__all__ = [
    "MAX_DESKTOP_BYTES",
    "MAX_DESKTOP_CANDIDATES",
    "MAX_DIRECTORY_DEPTH",
    "MAX_DIRECTORY_ENTRIES",
    "MAX_ICON_BYTES",
    "MAX_ICON_HEIGHT",
    "MAX_ICON_PIXELS",
    "MAX_ICON_WIDTH",
    "AllowedRoot",
    "IconMatch",
    "resolve_host_icon",
]
