"""POC tests for host desktop/PNG icon resolution."""

from pathlib import Path

from tests.support.host_icon_resolution import (
    MAX_DESKTOP_CANDIDATES,
    MAX_DIRECTORY_ENTRIES,
    MAX_ICON_BYTES,
    AllowedRoot,
    IconMatch,
    resolve_host_icon,
)

# Minimal valid PNG (1x1) bytes.
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00"
    b"\x00\x04\x00\x01\xa3\xa1\x1d\xeb\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _make_png(path: Path, size_bytes: int | None = None) -> None:
    if size_bytes is None:
        path.write_bytes(PNG_BYTES)
    else:
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * (size_bytes - 8))


def _install_path_guards(monkeypatch, predicate, touched) -> None:
    """Fail the test if production code touches a forbidden path."""
    for attr in ("open", "is_symlink", "resolve", "exists"):
        original = getattr(Path, attr)

        def guarded(self, *args, _original=original, _attr=attr, **kwargs):
            if predicate(str(self)):
                touched.append((_attr, str(self)))
                raise AssertionError(f"{_attr} touched forbidden path: {self}")
            return _original(self, *args, **kwargs)

        monkeypatch.setattr(Path, attr, guarded)


def test_positive_resolves_valid_png(tmp_path: Path) -> None:
    root = tmp_path
    icon = root / "icon.png"
    _make_png(icon)
    desktop = root / "app.desktop"
    desktop.write_text(
        "[Desktop Entry]\nName=App\nExec=/usr/bin/foo\nIcon=icon.png\nType=Application\n",
        encoding="utf-8",
    )

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "desktop"
    assert match.icon_path == icon
    assert isinstance(match, IconMatch)


def test_explicit_contained_desktop_resolves(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    icon = root / "icon.png"
    _make_png(icon)
    desktop = root / "app.desktop"
    desktop.write_text(_desktop_text(icon), encoding="utf-8")

    match = resolve_host_icon(roots=[root], desktop_files=[desktop], query="foo")

    assert match.source == "desktop"
    assert match.icon_path == icon


def test_ambiguous_returns_neutral(tmp_path: Path) -> None:
    root = tmp_path
    _make_png(root / "icon.png")
    for name in ("a.desktop", "b.desktop"):
        (root / name).write_text(
            "[Desktop Entry]\nName=App\nExec=/usr/bin/foo\nIcon=icon.png\nType=Application\n",
            encoding="utf-8",
        )

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_missing_returns_neutral(tmp_path: Path) -> None:
    root = tmp_path
    _make_png(root / "icon.png")

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_malformed_returns_neutral(tmp_path: Path) -> None:
    root = tmp_path
    _make_png(root / "icon.png")
    (root / "bad.desktop").write_text("this is not a desktop file\nfoo=bar", encoding="utf-8")

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_symlink_escape_returns_neutral(tmp_path: Path) -> None:
    root = tmp_path
    real_icon = root / "real.png"
    _make_png(real_icon)
    link_icon = root / "link.png"
    link_icon.symlink_to(real_icon)
    assert link_icon.is_symlink()
    (root / "app.desktop").write_text(
        "[Desktop Entry]\nName=App\nExec=/usr/bin/foo\nIcon=link.png\nType=Application\n",
        encoding="utf-8",
    )

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_oversize_returns_neutral(tmp_path: Path) -> None:
    root = tmp_path
    _make_png(root / "icon.png", size_bytes=MAX_ICON_BYTES + 1)
    (root / "app.desktop").write_text(
        "[Desktop Entry]\nName=App\nExec=/usr/bin/foo\nIcon=icon.png\nType=Application\n",
        encoding="utf-8",
    )

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_invalid_png_returns_neutral(tmp_path: Path) -> None:
    root = tmp_path
    (root / "icon.jpg").write_bytes(PNG_BYTES)
    (root / "app.desktop").write_text(
        "[Desktop Entry]\nName=App\nExec=/usr/bin/foo\nIcon=icon.jpg\nType=Application\n",
        encoding="utf-8",
    )

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_unknown_returns_neutral(tmp_path: Path) -> None:
    root = tmp_path
    _make_png(root / "icon.png")
    (root / "app.desktop").write_text(
        "[Desktop Entry]\nName=App\nExec=/usr/bin/foo\nIcon=icon.png\nType=Application\n",
        encoding="utf-8",
    )

    match = resolve_host_icon(roots=[root], query="bar")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_no_execute_returns_neutral(tmp_path: Path) -> None:
    root = tmp_path
    _make_png(root / "icon.png")
    (root / "app.desktop").write_text(
        "[Desktop Entry]\nName=App\nIcon=icon.png\nType=Application\n",
        encoding="utf-8",
    )

    # Match by desktop basename instead of executable.
    match = resolve_host_icon(roots=[root], desktop="app.desktop")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_neutral_on_no_identity(tmp_path: Path) -> None:
    root = tmp_path
    _make_png(root / "icon.png")
    (root / "app.desktop").write_text(
        "[Desktop Entry]\nName=App\nExec=/usr/bin/foo\nIcon=icon.png\nType=Application\n",
        encoding="utf-8",
    )

    match = resolve_host_icon(roots=[root])

    assert match.source == "neutral"
    assert match.icon_path is None


def test_absolute_icon_path_and_allowed_root(tmp_path: Path) -> None:
    root = tmp_path
    icon = root / "icon.png"
    _make_png(icon)
    (root / "app.desktop").write_text(
        f"[Desktop Entry]\nName=App\nExec=/usr/bin/foo\nIcon={icon}\nType=Application\n",
        encoding="utf-8",
    )

    match = resolve_host_icon(roots=[AllowedRoot.sentinel(root)], query="foo")

    assert match.source == "desktop"
    assert match.icon_path == icon


def test_lexical_escape_returns_neutral(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _make_png(outside / "icon.png")
    (root / "app.desktop").write_text(
        "[Desktop Entry]\nName=App\nExec=/usr/bin/foo\nIcon=../outside/icon.png\nType=Application\n",
        encoding="utf-8",
    )

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_absolute_icon_escape_returns_neutral(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    icon = outside / "icon.png"
    _make_png(icon)
    (root / "app.desktop").write_text(
        f"[Desktop Entry]\nName=App\nExec=/usr/bin/foo\nIcon={icon}\nType=Application\n",
        encoding="utf-8",
    )

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_tryexec_escape_returns_neutral(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    icon = root / "icon.png"
    _make_png(icon)
    (root / "app.desktop").write_text(
        "[Desktop Entry]\nName=App\nExec=/usr/bin/foo\nTryExec=/etc/passwd"
        "\nIcon=icon.png\nType=Application\n",
        encoding="utf-8",
    )

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_relative_tryexec_is_unverifiable(tmp_path: Path) -> None:
    root = tmp_path
    _make_png(root / "icon.png")
    (root / "app.desktop").write_text(
        "[Desktop Entry]\nName=App\nExec=/usr/bin/foo\nTryExec=definitely-not-here"
        "\nIcon=icon.png\nType=Application\n",
        encoding="utf-8",
    )

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_symlink_component_escape_returns_neutral(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    icon = outside / "icon.png"
    _make_png(icon)
    link = root / "escape.png"
    link.symlink_to(icon)

    (root / "app.desktop").write_text(
        "[Desktop Entry]\nName=App\nExec=/usr/bin/foo\nIcon=escape.png\nType=Application\n",
        encoding="utf-8",
    )

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_explicit_desktop_file_escape_returns_neutral(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    icon = outside / "icon.png"
    _make_png(icon)
    desktop = outside / "app.desktop"
    desktop.write_text(
        f"[Desktop Entry]\nName=App\nExec=/usr/bin/foo\nIcon={icon}\nType=Application\n",
        encoding="utf-8",
    )

    match = resolve_host_icon(roots=[root], desktop_files=[desktop], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_dbus_activatable_without_exec(tmp_path: Path) -> None:
    root = tmp_path
    icon = root / "icon.png"
    _make_png(icon)
    (root / "app.desktop").write_text(
        f"[Desktop Entry]\nName=App\nIcon={icon}\nType=Application\nDBusActivatable=true\n",
        encoding="utf-8",
    )

    match = resolve_host_icon(roots=[root], desktop="app.desktop")

    assert match.source == "desktop"
    assert match.icon_path == icon


def _desktop_text(icon: Path) -> str:
    return f"[Desktop Entry]\nName=App\nExec=/usr/bin/foo\nIcon={icon}\nType=Application\n"


def test_symlink_parent_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    icon = outside / "icon.png"
    _make_png(icon)
    (outside / "app.desktop").write_text(_desktop_text(icon), encoding="utf-8")
    link = root / "link"
    link.symlink_to(outside, target_is_directory=True)

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_absolute_icon_path_outside_roots(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside_icon = tmp_path / "outside.png"
    _make_png(outside_icon)
    (root / "app.desktop").write_text(
        f"[Desktop Entry]\nName=App\nExec=/usr/bin/foo\nIcon={outside_icon}\nType=Application\n",
        encoding="utf-8",
    )

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_tryexec_outside_roots(tmp_path: Path) -> None:
    root = tmp_path
    _make_png(root / "icon.png")
    (root / "app.desktop").write_text(
        "[Desktop Entry]\nName=App\nExec=/usr/bin/foo\nIcon=icon.png"
        "\nType=Application\nTryExec=/private/probe\n",
        encoding="utf-8",
    )

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_candidate_cap_min(tmp_path: Path) -> None:
    root = tmp_path
    icon = root / "icon.png"
    _make_png(icon)
    for i in range(MAX_DESKTOP_CANDIDATES + 1):
        (root / f"app{i}.desktop").write_text(
            _desktop_text(icon),
            encoding="utf-8",
        )

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_over_entries_limit(tmp_path: Path) -> None:
    root = tmp_path
    for i in range(MAX_DIRECTORY_ENTRIES + 1):
        (root / f"entry{i}.desktop").write_text(
            _desktop_text(Path("icon.png")),
            encoding="utf-8",
        )

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_global_limits_across_roots(tmp_path: Path) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    icon_a = root_a / "icon.png"
    icon_b = root_b / "icon.png"
    _make_png(icon_a)
    _make_png(icon_b)
    for i in range(33):
        (root_a / f"app{i}.desktop").write_text(
            _desktop_text(icon_a),
            encoding="utf-8",
        )
        (root_b / f"app{i}.desktop").write_text(
            _desktop_text(icon_b),
            encoding="utf-8",
        )

    match = resolve_host_icon(roots=[root_a, root_b], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_unreadable_subtree(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path
    _make_png(root / "icon.png")
    (root / "app.desktop").write_text(
        _desktop_text(root / "icon.png"),
        encoding="utf-8",
    )
    import tests.support.host_icon_resolution as mod

    def boom(*_args, **_kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(mod.os, "scandir", boom)

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_unreadable_subtree_cannot_produce_positive_match(tmp_path: Path, monkeypatch) -> None:
    """An unreadable subtree must abort discovery, never yield a "sole" match."""
    root = tmp_path / "root"
    root.mkdir()
    icon = root / "icon.png"
    _make_png(icon)
    (root / "a.desktop").write_text(_desktop_text(icon), encoding="utf-8")
    blocked = root / "sub" / "blocked"
    blocked.mkdir(parents=True)
    (blocked / "z.desktop").write_text(_desktop_text(icon), encoding="utf-8")

    real_lstat = Path.lstat
    real_stat = Path.stat
    probed: list[str] = []

    def guarded_lstat(self, *args, **kwargs):
        if str(self) == str(blocked):
            probed.append(str(self))
            raise PermissionError("denied")
        return real_lstat(self, *args, **kwargs)

    def guarded_stat(self, *args, **kwargs):
        # Pre-fix classification used stat-backed is_dir()/is_file(), which
        # swallow OSError and silently skip the subtree.
        if str(self) == str(blocked):
            raise PermissionError("denied")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", guarded_lstat)
    monkeypatch.setattr(Path, "stat", guarded_stat)

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None
    assert probed == [str(blocked)]


def test_explicit_candidates_beyond_limit(tmp_path: Path) -> None:
    root = tmp_path
    paths = [root / f"x{i}.desktop" for i in range(300)]

    match = resolve_host_icon(roots=[root], query="foo", desktop_files=paths)

    assert match.source == "neutral"
    assert match.icon_path is None


def test_empty_roots_with_explicit_candidates_returns_neutral(tmp_path: Path, monkeypatch) -> None:
    import tests.support.host_icon_resolution as mod

    outside = tmp_path / "outside.desktop"
    outside.write_text(_desktop_text(outside), encoding="utf-8")
    touched: list[tuple[str, str]] = []
    _install_path_guards(monkeypatch, lambda text: text == str(outside), touched)
    read_calls: list[tuple] = []
    monkeypatch.setattr(mod, "_read_desktop", lambda *args, **kw: read_calls.append(args))

    match = resolve_host_icon(roots=[], desktop_files=[outside], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None
    assert touched == []
    assert read_calls == []


def test_rejected_explicit_candidates_exhaust_shared_budget(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "root"
    root.mkdir()
    icon = root / "icon.png"
    _make_png(icon)
    valid = root / "app.desktop"
    valid.write_text(_desktop_text(icon), encoding="utf-8")
    outside_dir = tmp_path / "outside"
    outside = [outside_dir / f"x{i}.desktop" for i in range(MAX_DESKTOP_CANDIDATES)]
    forbidden = {str(path) for path in outside}
    touched: list[tuple[str, str]] = []
    _install_path_guards(monkeypatch, lambda text: text in forbidden, touched)

    match = resolve_host_icon(roots=[root], desktop_files=[*outside, valid], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None
    assert touched == []


def test_directory_enumeration_stops_at_entry_budget(tmp_path: Path, monkeypatch) -> None:
    import tests.support.host_icon_resolution as mod

    root = tmp_path
    icon = root / "icon.png"
    _make_png(icon)
    (root / "app.desktop").write_text(_desktop_text(icon), encoding="utf-8")
    for i in range(MAX_DIRECTORY_ENTRIES):
        (root / f"pad{i}.txt").write_text("x", encoding="utf-8")

    real_scandir = mod.os.scandir
    yielded = {"count": 0}

    class _CountingScan:
        def __init__(self, iterator) -> None:
            self._iterator = iterator

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            self._iterator.close()
            return False

        def __iter__(self):
            return self

        def __next__(self):
            entry = next(self._iterator)
            yielded["count"] += 1
            return entry

    def counting_scandir(path):
        return _CountingScan(real_scandir(path))

    monkeypatch.setattr(mod.os, "scandir", counting_scandir)

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None
    assert yielded["count"] <= MAX_DIRECTORY_ENTRIES + 1


def test_unreadable_competing_desktop_returns_neutral(tmp_path: Path, monkeypatch) -> None:
    import tests.support.host_icon_resolution as mod

    root = tmp_path
    icon = root / "icon.png"
    _make_png(icon)
    (root / "a.desktop").write_text(_desktop_text(icon), encoding="utf-8")
    (root / "b.desktop").write_text(_desktop_text(icon), encoding="utf-8")
    real_read = mod._read_desktop

    def selective(path, root_arg):
        if path.name == "b.desktop":
            raise mod._IncompleteDiscovery("unreadable")
        return real_read(path, root_arg)

    monkeypatch.setattr(mod, "_read_desktop", selective)

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_parent_component_with_symlink_never_probes_outside(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _make_png(outside / "icon.png")
    (root / "link").symlink_to(outside, target_is_directory=True)
    (root / "app.desktop").write_text(
        _desktop_text(Path("link/../outside/icon.png")), encoding="utf-8"
    )
    touched: list[tuple[str, str]] = []
    _install_path_guards(
        monkeypatch,
        lambda text: text.startswith(str(outside)) or ".." in Path(text).parts,
        touched,
    )

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None
    assert touched == []


def test_global_entry_budget_exhaustion_across_roots_is_neutral(tmp_path: Path) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    icon = root_a / "icon.png"
    _make_png(icon)
    (root_a / "app.desktop").write_text(_desktop_text(icon), encoding="utf-8")
    for i in range(MAX_DIRECTORY_ENTRIES - 2):
        (root_a / f"pad{i}.txt").write_text("x", encoding="utf-8")
    (root_b / "extra.txt").write_text("x", encoding="utf-8")

    match = resolve_host_icon(roots=[root_a, root_b], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_competing_match_beyond_entry_budget_is_neutral(tmp_path: Path) -> None:
    root = tmp_path
    icon = root / "icon.png"
    _make_png(icon)
    (root / "app.desktop").write_text(_desktop_text(icon), encoding="utf-8")
    (root / "zzz.desktop").write_text(_desktop_text(icon), encoding="utf-8")
    for i in range(MAX_DIRECTORY_ENTRIES - 1):
        (root / f"pad{i}.txt").write_text("x", encoding="utf-8")

    match = resolve_host_icon(roots=[root], query="foo")

    assert match.source == "neutral"
    assert match.icon_path is None


def test_symlink_parent_blocks_descendant_probe(monkeypatch) -> None:
    import tests.support.host_icon_resolution as mod

    root = Path("/fixture/root")
    link = root / "link"
    target = link / "secret.desktop"
    probes: list[Path] = []

    def probe(path):
        probes.append(path)
        assert path == link, f"forbidden descendant/root probe: {path}"
        return True

    monkeypatch.setattr(Path, "is_symlink", probe)

    assert mod._symlink_between(target, root)
    assert probes == [link]


def test_relative_explicit_retains_absolute_path_without_cwd_access(tmp_path, monkeypatch) -> None:
    import tests.support.host_icon_resolution as mod

    root = tmp_path / "root"
    root.mkdir()
    icon = root / "icon.png"
    _make_png(icon)
    desktop = root / "app.desktop"
    desktop.write_text(_desktop_text(Path("icon.png")), encoding="utf-8")
    allowed = AllowedRoot(root)
    touched: list[tuple[str, Path]] = []
    reads: list[Path] = []
    real_read = mod._read_desktop

    def read(path, root_arg):
        reads.append(path)
        return real_read(path, root_arg)

    for attr in ("open", "stat", "lstat", "is_symlink", "resolve", "exists", "is_file", "is_dir"):
        original = getattr(Path, attr)

        def guarded(path, *args, _original=original, _attr=attr, **kwargs):
            if not path.is_absolute():
                touched.append((_attr, path))
                raise AssertionError(f"cwd-relative access: {_attr} {path}")
            return _original(path, *args, **kwargs)

        monkeypatch.setattr(Path, attr, guarded)
    monkeypatch.setattr(mod, "_read_desktop", read)

    match = resolve_host_icon(roots=[allowed], desktop_files=["app.desktop"], query="foo")

    assert touched == []
    assert match == IconMatch(source="desktop", icon_path=icon)
    assert reads == [desktop]
    assert mod._desktop_entries([allowed], ["app.desktop"]) == ([desktop], False)


def test_relative_explicit_multiple_root_interpretations_are_rejected(tmp_path) -> None:
    import tests.support.host_icon_resolution as mod

    roots = [AllowedRoot(tmp_path / name) for name in ("a", "b")]

    assert mod._desktop_entries(roots, ["app.desktop"]) == ([], False)
    assert mod._desktop_entries(roots[::-1], ["app.desktop"]) == ([], False)
    expected = roots[0].path / "app.desktop"
    assert mod._desktop_entries([roots[0], roots[0]], ["app.desktop"]) == ([expected], False)


def test_symlink_walk_rejects_lexical_escape_without_probes(monkeypatch) -> None:
    import tests.support.host_icon_resolution as mod

    probes: list[Path] = []

    def forbidden(path):
        probes.append(path)
        raise AssertionError(f"lexically rejected path probed: {path}")

    monkeypatch.setattr(Path, "is_symlink", forbidden)
    root = Path("/fixture/root")

    assert mod._symlink_between(root / ".." / "secret.desktop", root)
    assert mod._symlink_between(Path("/outside/secret.desktop"), root)
    assert mod._symlink_between(root / "app.desktop", root / "..")
    assert probes == []


def test_symlink_walk_probe_error_is_incomplete(monkeypatch) -> None:
    import pytest

    import tests.support.host_icon_resolution as mod

    def denied(_path):
        raise PermissionError("fixture probe unavailable")

    monkeypatch.setattr(Path, "is_symlink", denied)

    with pytest.raises(mod._IncompleteDiscovery):
        mod._symlink_between(Path("/fixture/root/app.desktop"), Path("/fixture/root"))
