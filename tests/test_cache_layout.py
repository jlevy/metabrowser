"""The application-home resolver, the ``f01`` skeleton, and its separation from browsing.

Every home here is temporary. The browsing tests point ``METABROWSER_HOME`` at a missing,
a permissive, and a symlinked directory, run ordinary local browsing both in process and
as a real ``metab`` subprocess, and prove the application home was never resolved,
validated, or created.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import textwrap
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from metabrowser import home as home_module
from metabrowser.cache import layout as layout_module
from metabrowser.cache.atomic import write_record_atomic
from metabrowser.cache.layout import (
    FORMAT_HISTORY,
    LAYOUT_FORMAT,
    MIGRATIONS,
    FutureLayoutFormatError,
    LayoutError,
    format_number,
    migrate_layout,
    open_cache,
    read_config,
    read_layout,
)
from metabrowser.cache.locks import application_home_lock
from metabrowser.cache.records import CacheLayout
from metabrowser.cli.main import _app
from metabrowser.home import (
    CACHEDIR_TAG_CONTENT,
    CACHEDIR_TAG_SIGNATURE,
    DEFAULT_HOME_NAME,
    F01_DIRECTORIES,
    METABROWSER_HOME_ENV,
    ApplicationHomeError,
    PrivateStorageError,
    PrivateStorageViolation,
    application_home,
    ensure_home,
    write_private_file_atomic,
)

posix_only = pytest.mark.skipif(os.name != "posix", reason="owner-only storage is POSIX-only")
CHILD_TIMEOUT = 120


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.lstat(path).st_mode)


def _content(path: Path, mode: int) -> object:
    """What an entry holds: a link's target, a file's bytes, or nothing for a directory."""

    if stat.S_ISLNK(mode):
        return os.readlink(path)
    if not stat.S_ISREG(mode):
        return None
    try:
        return path.read_bytes()
    except OSError as error:
        return type(error).__name__


def _snapshot(root: Path) -> dict[str, tuple[int, int, object]]:
    """Every entry below *root* (links not followed) with its mode, inode, and content."""

    status = os.lstat(root)
    entries: dict[str, tuple[int, int, object]] = {".": (status.st_mode, status.st_ino, None)}
    for path in sorted(root.rglob("*")):
        status = os.lstat(path)
        entries[str(path.relative_to(root))] = (
            status.st_mode,
            status.st_ino,
            _content(path, status.st_mode),
        )
    return entries


# ── Resolution ─────────────────────────────────────────────────────


def test_the_default_home_is_dot_metabrowser_in_the_user_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    assert application_home({}) == tmp_path / DEFAULT_HOME_NAME
    assert not (tmp_path / DEFAULT_HOME_NAME).exists()


def test_metabrowser_home_overrides_the_default_without_touching_it(tmp_path: Path) -> None:
    chosen = tmp_path / "missing" / "home"

    assert application_home({METABROWSER_HOME_ENV: str(chosen)}) == chosen
    assert not (tmp_path / "missing").exists()


def test_the_process_environment_is_the_default_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(METABROWSER_HOME_ENV, str(tmp_path / "home"))

    assert application_home() == tmp_path / "home"


@pytest.mark.parametrize("value", ["", "relative/home", "~/home", "/tmp/../home"])
def test_an_unusable_metabrowser_home_is_refused_rather_than_ignored(value: str) -> None:
    with pytest.raises(ApplicationHomeError, match="METABROWSER_HOME"):
        application_home({METABROWSER_HOME_ENV: value})


# ── Skeleton ───────────────────────────────────────────────────────


@posix_only
def test_ensure_home_creates_the_private_f01_skeleton_and_cachedir_tag(tmp_path: Path) -> None:
    home = tmp_path / "home"

    cache_root = ensure_home(home)

    assert cache_root == home / "cache"
    assert _mode(home) == 0o700
    for directory in F01_DIRECTORIES:
        assert (home / directory).is_dir(), directory
        assert _mode(home / directory) == 0o700, directory
    tag = home / "cache/CACHEDIR.TAG"
    assert tag.read_bytes() == CACHEDIR_TAG_CONTENT
    assert tag.read_bytes().startswith(CACHEDIR_TAG_SIGNATURE)
    assert _mode(tag) == 0o600
    assert not (home / "config.yml").exists()
    assert not (home / "cache/layout.yml").exists()


@posix_only
def test_ensure_home_is_idempotent_and_keeps_a_valid_tag(tmp_path: Path) -> None:
    home = tmp_path / "home"
    ensure_home(home)
    tag = home / "cache/CACHEDIR.TAG"
    write_private_file_atomic(home, "cache/CACHEDIR.TAG", CACHEDIR_TAG_SIGNATURE + b"\n# mine\n")
    before = _snapshot(home)

    ensure_home(home)

    assert _snapshot(home) == before
    assert tag.read_bytes().endswith(b"# mine\n")


@posix_only
@pytest.mark.parametrize("content", [b"", b"Signature: 00000000\n"], ids=["torn", "foreign"])
def test_ensure_home_replaces_a_tag_without_the_signature(tmp_path: Path, content: bytes) -> None:
    home = tmp_path / "home"
    ensure_home(home)
    write_private_file_atomic(home, "cache/CACHEDIR.TAG", content)

    ensure_home(home)

    assert (home / "cache/CACHEDIR.TAG").read_bytes() == CACHEDIR_TAG_CONTENT


@posix_only
def test_ensure_home_refuses_a_permissive_home_without_repairing_it(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    home.chmod(0o755)

    with pytest.raises(PrivateStorageError) as refused:
        ensure_home(home)

    assert refused.value.violation is PrivateStorageViolation.PERMISSIVE
    assert _mode(home) == 0o755
    assert list(home.iterdir()) == []


# ── Local browsing never touches the application home ──────────────


def _browsing_root(tmp_path: Path) -> Path:
    root = tmp_path / "browse"
    root.mkdir()
    (root / "README.md").write_text("# Local\n")
    return root


def _home_variants(tmp_path: Path) -> dict[str, Path]:
    permissive = tmp_path / "permissive-home"
    permissive.mkdir()
    permissive.chmod(0o777)
    target = tmp_path / "symlink-target"
    target.mkdir()
    target.chmod(0o755)
    link = tmp_path / "symlinked-home"
    link.symlink_to(target, target_is_directory=True)
    return {
        "missing": tmp_path / "missing-home",
        "permissive": permissive,
        "symlinked": link,
    }


_FORBIDDEN_CALLS = (
    "application_home",
    "ensure_home",
    "validate_private_home",
    "ensure_private_directory",
    "open_private_file",
    "write_private_file_atomic",
)


@pytest.mark.parametrize("variant", ["missing", "permissive", "symlinked"])
def test_local_browsing_in_process_never_calls_the_application_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str
) -> None:
    root = _browsing_root(tmp_path)
    chosen = _home_variants(tmp_path)[variant]
    monkeypatch.setenv(METABROWSER_HOME_ENV, str(chosen))
    before = _snapshot(tmp_path)
    calls: list[str] = []

    def forbid(name: str) -> Any:
        def refuse(*_args: object, **_kwargs: object) -> Any:
            calls.append(name)
            raise AssertionError(f"local browsing called metabrowser.home.{name}")

        return refuse

    for name in _FORBIDDEN_CALLS:
        monkeypatch.setattr(home_module, name, forbid(name))
    runner = CliRunner()

    with (
        patch("metabrowser.cli.serve._QuietForceExitServer"),
        patch("metabrowser.cli.serve.find_available_local_port", return_value=8411),
    ):
        served = runner.invoke(_app, [str(root), "--no-open"])
    api = runner.invoke(_app, [str(root), "--api", "/api/tree?depth=1"])
    shown = runner.invoke(_app, [str(root), "--show", "README.md"])

    assert served.exit_code == 0, served.output
    assert api.exit_code == 0, api.output
    assert shown.exit_code == 0, shown.output
    assert calls == []
    assert _snapshot(tmp_path) == before


@posix_only
@pytest.mark.parametrize("variant", ["missing", "permissive", "symlinked"])
def test_metab_browsing_a_local_directory_never_creates_or_imports_the_home(
    tmp_path: Path, variant: str
) -> None:
    root = _browsing_root(tmp_path)
    chosen = _home_variants(tmp_path)[variant]
    before = _snapshot(tmp_path)
    script = textwrap.dedent(
        """
        import atexit, json, sys
        def report():
            loaded = sorted(
                name for name in sys.modules
                if name == "metabrowser.home" or name.startswith("metabrowser.cache")
            )
            sys.stderr.write("\\nloaded-modules:" + json.dumps(loaded) + "\\n")
        atexit.register(report)
        sys.argv = ["metab", *sys.argv[1:]]
        from metabrowser.cli.entrypoint import main
        main()
        """
    )
    environment = {**os.environ, METABROWSER_HOME_ENV: str(chosen)}

    result = subprocess.run(
        [sys.executable, "-c", script, str(root), "--api", "/api/tree?depth=1"],
        capture_output=True,
        text=True,
        env=environment,
        timeout=CHILD_TIMEOUT,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert '"tree"' in result.stdout
    loaded = json.loads(result.stderr.rpartition("loaded-modules:")[2])
    # The server registers the /api/cache/ route table, which imports the rest of the
    # cache and the application home only inside a cache request.
    assert loaded == ["metabrowser.cache", "metabrowser.cache.routes"]
    assert _snapshot(tmp_path) == before


# ── Layout format, migration, and config ───────────────────────────


_LAYOUT_HEADER = (
    "softschema:\n"
    "  contract: com.github.jlevy.metabrowser.cache:CacheLayout/{version}\n"
    "  envelope: layout\n"
    "  status: enforced\n"
)
_CONFIG_HEADER = (
    "softschema:\n"
    "  contract: com.github.jlevy.metabrowser.config:ApplicationConfig/v1\n"
    "  envelope: config\n"
    "  status: permissive\n"
)


@pytest.fixture
def cache_home(tmp_path: Path) -> Path:
    """A prepared skeleton whose home lock file exists, as after any earlier cache use.

    Taking a lock creates its lock file the first time; with that file present, a
    refused migration must leave every entry in the home exactly as it was.
    """

    home = tmp_path / "home"
    ensure_home(home)
    application_home_lock(home).release()
    return home


def _write_layout(home: Path, fmt: str, *, version: str = "v1", extra: str = "") -> None:
    text = _LAYOUT_HEADER.format(version=version)
    text += f"layout:\n  format: {fmt}\n  created_by: 0.11.0\n{extra}"
    write_private_file_atomic(home, "cache/layout.yml", text.encode())


def _write_config(home: Path, body: str) -> None:
    write_private_file_atomic(home, "config.yml", (_CONFIG_HEADER + body).encode())


def _record_writes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    writes: list[str] = []
    real_record = write_record_atomic
    real_file = write_private_file_atomic

    def record_write(home: Path, relative_path: str, *args: Any, **kwargs: Any) -> None:
        writes.append(relative_path)
        real_record(home, relative_path, *args, **kwargs)

    def file_write(home: Path, relative_path: str, *args: Any, **kwargs: Any) -> None:
        writes.append(relative_path)
        real_file(home, relative_path, *args, **kwargs)

    monkeypatch.setattr(layout_module, "write_record_atomic", record_write)
    monkeypatch.setattr(layout_module, "write_private_file_atomic", file_write)
    return writes


def test_the_current_format_ends_the_history_and_every_older_format_migrates() -> None:
    assert FORMAT_HISTORY[-1] == LAYOUT_FORMAT == "f01"
    assert set(MIGRATIONS) == set(FORMAT_HISTORY[:-1])
    assert [format_number(value) for value in FORMAT_HISTORY] == sorted(
        {format_number(value) for value in FORMAT_HISTORY}
    )


@posix_only
def test_a_new_home_publishes_its_layout_and_then_its_config(
    cache_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writes = _record_writes(monkeypatch)

    outcome = migrate_layout(cache_home, version="0.11.0")

    assert writes == ["cache/layout.yml", "config.yml"]
    assert outcome.layout == CacheLayout(format="f01", created_by="0.11.0")
    assert outcome.config.model_dump(mode="json") == {
        "format": "f01",
        "written_by": "0.11.0",
        "upgrades": [],
    }
    assert read_layout(cache_home) == outcome.layout
    assert read_config(cache_home) == outcome.config
    assert (cache_home / "config.yml").read_text().startswith("softschema:\n")
    assert _mode(cache_home / "config.yml") == 0o600


@posix_only
def test_reopening_a_current_home_writes_nothing(
    cache_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    migrate_layout(cache_home, version="0.11.0")
    before = _snapshot(cache_home)
    writes = _record_writes(monkeypatch)

    outcome = migrate_layout(cache_home, version="0.12.0")

    assert writes == []
    assert outcome.previous_format == "f01"
    assert _snapshot(cache_home) == before


@posix_only
@pytest.mark.parametrize(
    "setup",
    [
        lambda home: _write_layout(home, "f02"),
        lambda home: _write_layout(home, "f07", version="v3", extra="  shards: 256\n"),
        lambda home: (
            _write_layout(home, "f01"),
            _write_config(home, "config:\n  format: f02\n  written_by: 0.13.0\n  upgrades: []\n"),
        ),
    ],
    ids=["future-layout", "future-layout-contract", "future-config"],
)
def test_an_older_client_refuses_a_future_home_before_writing(
    cache_home: Path, setup: Callable[[Path], object]
) -> None:
    setup(cache_home)
    before = _snapshot(cache_home)
    contents = {
        path: (cache_home / path).read_bytes()
        for path in ("cache/layout.yml", "config.yml")
        if (cache_home / path).exists()
    }

    with pytest.raises(FutureLayoutFormatError, match="Upgrade Metabrowser") as refused:
        migrate_layout(cache_home, version="0.11.0")

    assert refused.value.supported == "f01"
    assert str(cache_home) not in str(refused.value)
    assert _snapshot(cache_home) == before
    assert all((cache_home / path).read_bytes() == data for path, data in contents.items())

    # Preparing the home for use reads the format before it creates or probes anything.
    with pytest.raises(FutureLayoutFormatError, match="Upgrade Metabrowser"):
        open_cache(cache_home, version="0.11.0")

    assert _snapshot(cache_home) == before
    assert all((cache_home / path).read_bytes() == data for path, data in contents.items())


@posix_only
@pytest.mark.parametrize("prepare", [open_cache, migrate_layout])
def test_a_shared_future_home_is_refused_before_its_modes_are_tightened(
    cache_home: Path,
    prepare: Callable[..., object],
) -> None:
    """The future-format answer must precede every change, repairs included."""

    _write_layout(cache_home, "f02")
    (cache_home / "cache").chmod(0o755)
    (cache_home / "cache/layout.yml").chmod(0o644)
    before = _snapshot(cache_home)

    with pytest.raises(FutureLayoutFormatError, match="Upgrade Metabrowser"):
        prepare(cache_home, version="0.11.0")

    assert _snapshot(cache_home) == before


@posix_only
def test_a_shared_but_readable_home_is_still_repaired_and_then_prepared(
    cache_home: Path,
) -> None:
    """Only a future format precedes repair; an ordinary shared home is repaired.

    The preflight reads with ``keep``, which neither tightens nor refuses an over-shared
    entry, so every one of them must still be repaired by the reads that follow it.
    """

    (cache_home / "cache").chmod(0o755)

    open_cache(cache_home, version="0.11.0")

    assert stat.S_IMODE((cache_home / "cache").stat().st_mode) == 0o700

    shared = {"cache": 0o755, "cache/layout.yml": 0o644, "config.yml": 0o644}
    for entry, mode in shared.items():
        (cache_home / entry).chmod(mode)

    opened = open_cache(cache_home, version="0.11.0")

    assert opened.layout.format == "f01"
    assert {entry: _mode(cache_home / entry) for entry in shared} == {
        "cache": 0o700,
        "cache/layout.yml": 0o600,
        "config.yml": 0o600,
    }


@posix_only
@pytest.mark.parametrize("prepare", [open_cache, migrate_layout])
def test_a_future_home_that_was_never_prepared_stays_uncreated(
    tmp_path: Path, prepare: Callable[..., object]
) -> None:
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    write_private_file_atomic(
        home,
        "config.yml",
        (
            _CONFIG_HEADER + "config:\n  format: f09\n  written_by: 0.99.0\n  upgrades: []\n"
        ).encode(),
    )
    before = _snapshot(home)

    with pytest.raises(FutureLayoutFormatError):
        prepare(home, version="0.11.0")

    assert _snapshot(home) == before
    assert not (home / "cache").exists()


@posix_only
def test_an_unreadable_config_is_refused_with_a_bounded_value_free_message(
    cache_home: Path,
) -> None:
    secret = "ghp-examplesecrettokenvalue"
    upgrades = "".join(f'    - {{version: "{secret}", at: "{secret}"}}\n' for _ in range(500))
    _write_config(
        cache_home,
        f'config:\n  format: f01\n  written_by: "{secret}"\n  upgrades:\n{upgrades}',
    )

    with pytest.raises(LayoutError) as refused:
        migrate_layout(cache_home, version="0.11.0")

    message = str(refused.value)
    assert len(message) <= 4096
    assert secret not in message
    assert str(cache_home) not in message


@posix_only
def test_migrations_run_in_order_and_publish_config_last(
    cache_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    migrate_layout(cache_home, version="0.11.0")
    _write_config(
        cache_home,
        "config:\n  format: f01\n  written_by: 0.11.0\n  upgrades: []\n"
        "  theme:\n    accent: teal\n  editor: vim\n",
    )
    seen: list[tuple[str, str | None]] = []

    def migration(name: str) -> Callable[[Path], None]:
        def migrate(home: Path) -> None:
            layout = read_layout(home, history=("f01", "f02", "f03"))
            seen.append((name, None if layout is None else layout.format))

        return migrate

    writes = _record_writes(monkeypatch)
    outcome = migrate_layout(
        cache_home,
        version="0.13.0",
        history=("f01", "f02", "f03"),
        migrations={"f01": migration("to-f02"), "f02": migration("to-f03")},
        now=lambda: "2026-12-01T00:00:00Z",
    )

    assert seen == [("to-f02", "f01"), ("to-f03", "f02")]
    assert writes == ["cache/layout.yml", "cache/layout.yml", "config.yml"]
    assert outcome.migrated_through == ("f02", "f03")
    assert outcome.layout.format == "f03"
    config = outcome.config.model_dump(mode="json")
    assert config["format"] == "f03"
    assert config["written_by"] == "0.13.0"
    assert config["upgrades"] == [{"version": "0.13.0", "at": "2026-12-01T00:00:00Z"}]
    assert config["theme"] == {"accent": "teal"}
    assert list(config) == ["format", "written_by", "upgrades", "theme", "editor"]


@posix_only
def test_an_interrupted_migration_resumes_from_its_last_published_step(cache_home: Path) -> None:
    migrate_layout(cache_home, version="0.11.0")
    calls: list[str] = []
    history = ("f01", "f02", "f03")

    def to_f02(_home: Path) -> None:
        calls.append("to-f02")

    def crashing_to_f03(_home: Path) -> None:
        calls.append("to-f03")
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        migrate_layout(
            cache_home,
            version="0.13.0",
            history=history,
            migrations={"f01": to_f02, "f02": crashing_to_f03},
        )
    assert read_layout(cache_home, history=history) == CacheLayout(
        format="f02", created_by="0.11.0"
    )
    config = read_config(cache_home, history=history)
    assert config is not None and config.format == "f01"

    def to_f03(_home: Path) -> None:
        calls.append("resumed-to-f03")

    outcome = migrate_layout(
        cache_home, version="0.13.0", history=history, migrations={"f01": to_f02, "f02": to_f03}
    )

    assert calls == ["to-f02", "to-f03", "resumed-to-f03"]
    assert outcome.layout.format == "f03"
    assert outcome.config.format == "f03"
    assert len(outcome.config.upgrades) == 1


@posix_only
def test_a_layout_ahead_of_its_config_republishes_only_the_config(
    cache_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    migrate_layout(cache_home, version="0.11.0")
    (cache_home / "config.yml").unlink()
    writes = _record_writes(monkeypatch)

    outcome = migrate_layout(cache_home, version="0.11.0")

    assert writes == ["config.yml"]
    assert outcome.config.format == "f01"


@posix_only
def test_a_missing_migration_is_a_programming_error(cache_home: Path) -> None:
    migrate_layout(cache_home, version="0.11.0")

    with pytest.raises(RuntimeError, match="no migration from layout format f01"):
        migrate_layout(cache_home, version="0.12.0", history=("f01", "f02"), migrations={})


@posix_only
@pytest.mark.parametrize(
    "setup",
    [
        lambda home: _write_layout(home, "f00"),
        lambda home: write_private_file_atomic(home, "cache/layout.yml", b"layout: [\n"),
        lambda home: _write_layout(home, "f01", extra="  schema: /tmp/any.schema.yaml\n"),
        lambda home: home_module.ensure_private_directory(home, "cache/sources/unknown"),
        lambda home: _write_config(
            home,
            "config:\n  format: f01\n  written_by: x\n  upgrades: []\n  github_token: secret\n",
        ),
        lambda home: write_private_file_atomic(
            home,
            "config.yml",
            (
                _CONFIG_HEADER.replace(
                    "status: permissive", "status: permissive\n  schema: /tmp/x.yaml"
                )
            ).encode()
            + b"config:\n  format: f01\n  written_by: x\n  upgrades: []\n",
        ),
        lambda home: write_private_file_atomic(home, "config.yml", b"format: f01\n"),
    ],
    ids=[
        "unreleased-older-format",
        "malformed-layout",
        "layout-with-undeclared-field",
        "entries-without-layout",
        "config-with-credential",
        "config-naming-a-schema",
        "config-without-header",
    ],
)
def test_an_unreadable_home_is_refused_and_left_unchanged(
    cache_home: Path, setup: Callable[[Path], object]
) -> None:
    setup(cache_home)
    before = _snapshot(cache_home)

    with pytest.raises(LayoutError) as refused:
        migrate_layout(cache_home, version="0.11.0")

    assert str(cache_home) not in str(refused.value)
    assert _snapshot(cache_home) == before


@posix_only
def test_open_cache_prepares_probes_migrates_and_sweeps(tmp_path: Path) -> None:
    home = tmp_path / "home"
    ensure_home(home)
    home_module.ensure_private_directory(home, "cache/staging/crashed-clone/objects")

    opened = open_cache(home, version="0.11.0")

    assert opened.home == home
    assert opened.layout.format == "f01"
    assert opened.config.format == "f01"
    assert opened.sweep.removed == ("cache/staging/crashed-clone",)
    assert not (home / "cache/staging/crashed-clone").exists()
    assert (home / "cache/CACHEDIR.TAG").exists()


@posix_only
def test_open_cache_resolves_metabrowser_home_when_no_home_is_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(METABROWSER_HOME_ENV, str(tmp_path / "chosen"))

    opened = open_cache(version="0.11.0")

    assert opened.home == tmp_path / "chosen"
    assert (tmp_path / "chosen/cache/layout.yml").is_file()


@posix_only
@pytest.mark.parametrize("prepare", [open_cache, migrate_layout])
@pytest.mark.parametrize(
    "directory",
    ["sources", "repository-stores", "quarantine", "provider-bindings", "provider-repositories"],
)
def test_unrecognized_durable_cache_is_refused_without_any_mutation(
    tmp_path: Path, prepare: Callable[..., object], directory: str
) -> None:
    home = tmp_path / "home"
    durable = home / "cache" / directory
    durable.mkdir(parents=True)
    home.chmod(0o700)
    data = durable / "unknown-record"
    data.write_bytes(b"unrecognized durable data")
    before = _snapshot(home)

    with pytest.raises(LayoutError, match="no cache/layout.yml"):
        prepare(home)

    assert _snapshot(home) == before
    assert data.read_bytes() == b"unrecognized durable data"


def _symlinked_config_beside_durable_entries(home: Path) -> None:
    """A dotfiles-style ``config.yml`` link, beside entries no layout describes."""

    home_module.ensure_private_directory(home, "cache/sources/some-entry")
    target = home.parent / "dotfiles-config.yml"
    target.write_text("softschema: {}\n")
    (home / "config.yml").unlink(missing_ok=True)
    os.symlink(target, home / "config.yml")


def _hard_linked_future_layout(home: Path) -> None:
    """A future ``cache/layout.yml`` whose bytes are reachable from outside the home."""

    home_module.ensure_private_directory(home, "cache")
    _write_layout(home, "f02")
    os.link(home / "cache/layout.yml", home.parent / "backup-of-layout.yml")


def _unreadable_future_layout(home: Path) -> None:
    """A future ``cache/layout.yml`` whose own permissions deny its owner a read."""

    home_module.ensure_private_directory(home, "cache")
    _write_layout(home, "f02")
    (home / "cache/layout.yml").chmod(0o200)


@posix_only
@pytest.mark.parametrize("prepare", [open_cache, migrate_layout])
@pytest.mark.parametrize("prepared", [False, True], ids=["bare-home", "existing-skeleton"])
@pytest.mark.parametrize(
    "damage",
    [
        _symlinked_config_beside_durable_entries,
        _hard_linked_future_layout,
        _unreadable_future_layout,
    ],
    ids=["symlinked-config", "hard-linked-layout", "unreadable-layout"],
)
def test_a_record_that_cannot_be_verified_is_refused_without_any_mutation(
    tmp_path: Path,
    prepare: Callable[..., object],
    prepared: bool,
    damage: Callable[[Path], None],
) -> None:
    """A record the preflight cannot read is an answer, not a reason to carry on.

    Nothing below may be created, probed, or repaired before the refusal: the home may
    hold entries this release must not adopt, and the unreadable record is exactly what
    would have said so.
    """

    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    if prepared:
        ensure_home(home)
    damage(home)
    before = _snapshot(home)

    with pytest.raises(PrivateStorageError) as refused:
        prepare(home, version="0.11.0")

    assert str(home) not in str(refused.value)
    assert _snapshot(home) == before
