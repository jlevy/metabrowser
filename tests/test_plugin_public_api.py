"""Public Python helpers used by installed plugin sidekicks."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import metabrowser
import metabrowser.plugin_api as plugin_api
from metabrowser import (
    ArtifactCompressionError,
    ArtifactDecompressionLimitError,
    ArtifactDecompressionTimeoutError,
    ArtifactPath,
    JsonlParseLimitError,
    create_parser,
    detect_adapter,
    extract_agent_charts_cached,
    paths_safe,
    register_root_callback,
    relativize_path,
    resolve_directory,
    resolve_path,
)
from metabrowser.paths_safe import _set_root_dir

PLUGIN_API_EXPORTS = {
    "ArtifactCompressionError",
    "ArtifactDecompressionLimitError",
    "ArtifactDecompressionTimeoutError",
    "ArtifactPath",
    "ContentReadError",
    "ContentRef",
    "ContentStat",
    "ContentUnavailableError",
    "ContentWindow",
    "JsonlParseLimitError",
    "LogEvent",
    "LogParser",
    "SourceCapabilities",
    "UnsupportedSourceCapabilityError",
    "create_parser",
    "detect_adapter",
    "extract_agent_charts_cached",
    "read_content_window",
    "register_log_adapter",
    "open_content",
    "register_root_callback",
    "relativize_path",
    "require_source_capability",
    "resolve_content",
    "resolve_content_container",
    "resolve_directory",
    "resolve_path",
    "served_root",
    "source_capabilities",
    "stat_content",
    "MAX_CONTAINER_INNER_DEPTH",
    # The table source protocol a source plugin implements (metabrowser.table_source).
    "MAX_SAFE_INTEGER",
    "TABLE_CARD_MAX_FIELDS",
    "TABLE_CELL_PREVIEW_CHARS",
    "TABLE_PAGE_CELLS_MAX",
    "TABLE_PAGE_ROWS_DEFAULT",
    "TABLE_PAGE_ROWS_MAX",
    "TABLE_RECORD_VALUE_BYTES",
    "TABLE_REQUEST_DEADLINE_SECONDS",
    "TABLE_TOKEN_MAX_CHARS",
    "BackrefCount",
    "Budget",
    "Cell",
    "FieldRef",
    "FieldType",
    "Filter",
    "FilterOp",
    "FolderTableHandle",
    "FolderTableSourceAdapter",
    "Order",
    "PageReason",
    "RecordNotFoundError",
    "RefFilter",
    "SourceUnreadableError",
    "TableCard",
    "TableField",
    "TableGroup",
    "TableHandle",
    "TableInfo",
    "TableNotFoundError",
    "TablePage",
    "TableQuery",
    "TableQueryError",
    "TableRecord",
    "TableRow",
    "TableSchema",
    "TableSource",
    "TableSourceAdapter",
    "TableSourceError",
    "blob_cell",
    "coerce_filter_value",
    "content_generation",
    "cut_utf8",
    "decode_cursor",
    "decode_key",
    "encode_cursor",
    "encode_key",
    "integer_cell",
    "page_columns",
    "page_row_limit",
    "parse_position_key",
    "parse_positional_cursor",
    "position_key",
    "positional_cursor",
    "real_cell",
    "stat_generation",
    "stored_cell",
    "text_cell",
    "PluginCacheUnavailableError",
    "extract_agent_charts_bytes",
    "jsonl_parse_max_bytes",
    "lookup_agent_charts",
    "plugin_cache_directory",
    "registered_log_adapters",
    "remember_agent_charts",
}


def test_public_export_contract_is_exact() -> None:
    assert set(plugin_api.__all__) == PLUGIN_API_EXPORTS
    assert set(metabrowser.__all__) == PLUGIN_API_EXPORTS | {"CLIError", "__version__"}


def test_sidekick_path_helpers_are_public_and_root_bounded(tmp_path: Path) -> None:
    original_root = paths_safe.ROOT_DIR
    try:
        _set_root_dir(tmp_path)
        folder = tmp_path / "reports%20"
        folder.mkdir()
        report = folder / "summary.md"
        report.write_text("# Summary\n")

        assert resolve_path("reports%2520/summary.md") == report
        root = resolve_path("")
        assert root == tmp_path
        assert root is not None and root.is_dir()
        assert resolve_directory("reports%2520") == folder
        assert resolve_path("../outside.txt") is None
        assert resolve_directory("reports%2520/summary.md") is None
        assert relativize_path(str(report)) == "reports%2520/summary.md"
    finally:
        _set_root_dir(original_root)


def test_sidekick_runtime_helpers_are_public() -> None:
    assert ArtifactPath.__name__ == "ArtifactPath"
    assert issubclass(ArtifactDecompressionTimeoutError, ArtifactDecompressionLimitError)
    assert issubclass(ArtifactDecompressionLimitError, ArtifactCompressionError)
    assert issubclass(JsonlParseLimitError, ValueError)
    assert create_parser("unknown").adapter_name == "unknown"
    assert callable(detect_adapter)
    assert callable(extract_agent_charts_cached)
    assert callable(register_root_callback)


def test_public_import_does_not_load_schema_dependencies() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import metabrowser; "
                "assert 'softschema' not in sys.modules; "
                "assert 'jsonschema' not in sys.modules; "
                "assert 'frontmatter_format' not in sys.modules"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_version_command_does_not_load_schema_dependencies() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; from metabrowser.cli.main import _app; "
                "_app(args=['--version'], standalone_mode=False); "
                "assert 'softschema' not in sys.modules; "
                "assert 'jsonschema' not in sys.modules; "
                "assert 'frontmatter_format' not in sys.modules"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


# What a pinned Git revision, a Git source, or ``--diff`` needs and a local folder does
# not. Loading any of it when the process starts is work every ``metab`` run pays, in
# every mode, whether or not a repository is ever opened. The measurements that put the
# line here are in explorations/performance-loop/experiments/exp-037.
_GIT_SOURCE_MODULES = (
    # The revision tree source, and the routes that answer from it.
    "metabrowser.git.tree_source",
    "metabrowser.git.content_routes",
    # The answers a pin keeps of when its files last changed (``--doctor`` reads
    # ``git.file_ages`` alone, to say whether the Git can).
    "metabrowser.git.file_ages_service",
    # Acquiring a Git source and serving its pin, and what a first clone reads Git's
    # progress with and reports it through.
    "metabrowser.cli.acquire_cli",
    "metabrowser.cli.git_pin_cli",
    "metabrowser.cli.selection",
    "metabrowser.cli.clone_report",
    "metabrowser.git.progress",
    # The ``--diff`` mode.
    "metabrowser.cli.diff_cli",
)
# A folder's server registers these and nothing else of their packages: each is a route
# table whose handlers import the rest when a request needs it.
_ROUTE_TABLE_ONLY = {
    "metabrowser.cache": {"metabrowser.cache.routes"},
    "metabrowser.builtin_plugins.github": {"metabrowser.builtin_plugins.github.sidekick"},
}

# One fresh interpreter importing the application and answering a request: under the
# suite's own timeout, so a child that hangs fails here and names what it was running.
_CHILD_TIMEOUT_S = 50

_REPORT_LOADED_MODULES = textwrap.dedent(
    """
    import atexit, json, sys
    def report():
        loaded = sorted(name for name in sys.modules if name.startswith("metabrowser."))
        sys.stderr.write("\\nloaded-modules:" + json.dumps(loaded) + "\\n")
    atexit.register(report)
    sys.argv = ["metab", *sys.argv[1:]]
    from metabrowser.cli.entrypoint import main
    main()
    """
)


def _modules_loaded_by(*args: str) -> set[str]:
    """Run ``metab`` with *args* in a fresh interpreter and return what it imported."""

    result = subprocess.run(
        [sys.executable, "-c", _REPORT_LOADED_MODULES, *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=_CHILD_TIMEOUT_S,
    )
    assert result.returncode == 0, result.stderr
    return set(json.loads(result.stderr.rpartition("loaded-modules:")[2]))


def test_folder_browsing_survives_omitting_the_collection_plugin(tmp_path: Path) -> None:
    records = tmp_path / "records"
    records.mkdir()
    (records / "ada.json").write_text(
        '{"softschema":{"contract":"example:Person/v1","envelope":"person"},'
        '"person":{"name":"Ada"}}'
    )
    script = textwrap.dedent(
        """
        import asyncio
        import importlib.resources
        import sys
        from pathlib import Path
        from unittest.mock import patch

        package = "metabrowser.builtin_plugins"
        builtin_root = Path(str(importlib.resources.files(package)))
        iterdir = Path.iterdir

        def without_collection(parent):
            return (
                child for child in iterdir(parent)
                if parent != builtin_root or child.name != "softschema"
            )

        sys.modules[package + ".softschema"] = None
        with patch.object(Path, "iterdir", without_collection):
            from metabrowser import server
        from metabrowser.cli.asgi_client import InProcessClient

        assert not server._DISCOVERY.errors, server._DISCOVERY.errors
        server._set_root_dir(Path(sys.argv[1]))

        async def verify():
            async with InProcessClient(server.app, label="without collection") as client:
                folder = await client.get("/api/file?path=records")
                assert [view["id"] for view in folder.json()["views"]] == ["overview", "treemap"]
                parsed = await client.get(
                    "/api/plugin/structured/parsed?projection=nodes&path=records/ada.json"
                )
                assert parsed.json()["status"] == "ready"
                assert (await client.get("/api/plugin/softschema/collection?path=records")).status_code == 404

        asyncio.run(verify())
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=_CHILD_TIMEOUT_S,
    )
    assert result.returncode == 0, result.stderr


def _git_source_modules_in(loaded: set[str]) -> list[str]:
    found = [name for name in _GIT_SOURCE_MODULES if name in loaded]
    for package, allowed in _ROUTE_TABLE_ONLY.items():
        found.extend(
            sorted(
                name for name in loaded if name.startswith(package + ".") and name not in allowed
            )
        )
    return found


def test_version_command_does_not_load_git_source_or_server_modules() -> None:
    loaded = _modules_loaded_by("--version")

    assert _git_source_modules_in(loaded) == []
    # Nor anything a server is made of: the version is known before a mode is chosen.
    for name in (
        "metabrowser.server",
        "metabrowser.source_routes",
        "metabrowser.mirror_refresh",
        "metabrowser.git.routes",
        "metabrowser.diff.adapters.git",
        # Nor owner-only storage and the recent targets list, which only a serve and the
        # --recent modes use.
        "metabrowser.home",
        "metabrowser.recent_targets",
    ):
        assert name not in loaded, name


# The routes a folder's page asks for. A handler that imports a pin's module before it
# checks the subject defers the cost to its first request instead of removing it:
# `/api/catalog` did, and its first answer on a folder cost a third more for it.
_FOLDER_ROUTES = (
    "/api/tree?depth=1",
    "/api/catalog",
    "/api/index/meta",
    "/api/index/progress",
    "/api/capabilities",
    "/api/file?path=README.md",
    "/api/kpress/render?path=README.md",
    "/api/rollup?path=&depth=1",
    "/api/activity",
    "/api/git/repo",
    "/api/source/status",
    "/api/identity",
    "/api/counterpart?page=/view/README.md",
)


@pytest.mark.parametrize(
    "mode",
    [*(("--api", route) for route in _FOLDER_ROUTES), ("--show", "README.md"), ("--walk",)],
    ids=[*_FOLDER_ROUTES, "show", "walk"],
)
def test_a_local_folder_does_not_load_git_source_modules(
    tmp_path: Path, mode: tuple[str, ...]
) -> None:
    root = tmp_path / "browse"
    root.mkdir()
    (root / "README.md").write_text("# Local\n")

    loaded = _modules_loaded_by(str(root), *mode)

    assert _git_source_modules_in(loaded) == []
    if mode[0] != "--walk":
        # The request went through the real server, so the absence above is not an
        # artifact of a mode that never builds the application.
        assert "metabrowser.server" in loaded


# The page itself, and a file's bytes: `--api` reaches only `/api/` routes, so these go
# through the same in-process client it uses, in the same kind of fresh interpreter. The
# shell's handler is where a pin's import is easiest to hoist, since it branches on the
# subject before it renders anything.
# Each with the status a folder's server answers: the bare origin redirects to the root's
# view, and a commit or pull-request address is a page whose own request says what the
# folder cannot show.
_SHELL_ROUTES = (
    ("/", 307),
    ("/view/", 200),
    ("/view/README.md", 200),
    ("/view/docs/", 200),
    ("/raw/README.md", 200),
    ("/commit/0123abc", 200),
    ("/pull/7", 200),
    ("/pull/7/files/src/app.py", 200),
    ("/pulls", 200),
)

_REPORT_LOADED_AFTER_REQUEST = textwrap.dedent(
    """
    import asyncio, json, sys
    from pathlib import Path
    from metabrowser import server
    from metabrowser.cli.asgi_client import InProcessClient

    async def answer(route):
        async with InProcessClient(server.app, label="shell") as client:
            return (await client.get(route)).status_code

    server._set_root_dir(Path(sys.argv[1]))
    status = asyncio.run(answer(sys.argv[2]))
    loaded = sorted(name for name in sys.modules if name.startswith("metabrowser."))
    sys.stdout.write(json.dumps({"status": status, "loaded": loaded}))
    """
)


@pytest.mark.parametrize(("route", "status"), _SHELL_ROUTES, ids=[r for r, _ in _SHELL_ROUTES])
def test_a_local_folders_page_does_not_load_git_source_modules(
    tmp_path: Path, route: str, status: int
) -> None:
    root = tmp_path / "browse"
    (root / "docs").mkdir(parents=True)
    (root / "README.md").write_text("# Local\n")

    result = subprocess.run(
        [sys.executable, "-c", _REPORT_LOADED_AFTER_REQUEST, str(root), route],
        check=False,
        capture_output=True,
        text=True,
        timeout=_CHILD_TIMEOUT_S,
    )
    assert result.returncode == 0, result.stderr
    answer = json.loads(result.stdout)

    assert answer["status"] == status, route
    assert _git_source_modules_in(set(answer["loaded"])) == []


# What `--present --dry-run` may load beyond what `metab --version` loads, which already
# holds the CLI, the serve mode's module, and what they import. The macOS app runs a dry
# run to check what a user types, so this is also its cost per link. A boundary stated
# against `--version` fails for anything added, where a list of forbidden modules fails
# only for what someone thought to list. Standard-library packages are named by their
# top-level name, since their submodules differ between Python versions.
# The `open_in` preference's reader (`metabrowser.open_in`) adds config.yml's name and
# bound and the owner-only file helpers it is read through, with what they import from
# the standard library: `secrets` and the `hmac` under it, and the layout of a `ctypes`
# structure. Importing them took 4 to 24 ms on 2026-11-18 on an Apple silicon Mac under
# a load average near 300 (`python -X importtime`).
_PRESENT_LOCAL_EXTRA = frozenset(
    {
        "metabrowser.cli.present",
        "metabrowser.config_file",
        "metabrowser.home",
        "metabrowser.invisible_chars",
    }
)
# The property-list reader, for a bundle's Info.plist, and the XML parser it uses; and
# what the preference's reader adds; and `unicodedata`, which `cli.present` imports for
# its own use and which `--version` used to load already, through `prettyfmt`, until the
# agent-log parsers moved out of core with their import of it.
_PRESENT_STDLIB_EXTRA = frozenset(
    {"_hmac", "ctypes", "hmac", "plistlib", "pyexpat", "secrets", "unicodedata", "xml"}
)
# A link adds the URL grammar, each provider's reducer without its provider, and the path
# encoding and revision grammar a page is spelled with.
_PRESENT_LINK_EXTRA = frozenset(
    {
        "metabrowser.builtin_plugins",
        "metabrowser.builtin_plugins.github",
        "metabrowser.builtin_plugins.github.urls",
        "metabrowser.cache",
        "metabrowser.cache.identity",
        "metabrowser.cache.providers",
        "metabrowser.cache.urls",
        "metabrowser.cli.selection_href",
        "metabrowser.git.tree_source",
        "metabrowser.git.wire",
    }
)

# Run with an audit hook: what the dry run imports, and every process it starts or
# address it connects to or looks up, which a list of modules would miss when it is
# reached through a module nobody listed.
_REPORT_LOADED_MODULES_AND_EFFECTS = textwrap.dedent(
    """
    import atexit, json, sys
    effects = []
    _WATCHED = ("subprocess.Popen", "os.posix_spawn", "os.exec", "os.system", "os.fork",
                "socket.connect", "socket.getaddrinfo", "socket.gethostbyname")
    def hook(event, args):
        if event.startswith(_WATCHED):
            effects.append(event)
    sys.addaudithook(hook)
    def report():
        sys.stderr.write("\\nloaded-modules:" + json.dumps(
            {"modules": sorted(sys.modules), "effects": effects}) + "\\n")
    atexit.register(report)
    sys.argv = ["metab", *sys.argv[1:]]
    from metabrowser.cli.entrypoint import main
    main()
    """
)


def _loaded_and_effects(*args: str) -> tuple[set[str], list[str], int]:
    result = subprocess.run(
        [sys.executable, "-c", _REPORT_LOADED_MODULES_AND_EFFECTS, *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=_CHILD_TIMEOUT_S,
    )
    report = json.loads(result.stderr.rpartition("loaded-modules:")[2])
    return set(report["modules"]), report["effects"], result.returncode


def _beyond(loaded: set[str], baseline: set[str]) -> set[str]:
    """What *loaded* adds to *baseline*, a standard-library module by its package."""

    return {
        name if name.startswith("metabrowser.") else name.partition(".")[0]
        for name in loaded - baseline
    }


@pytest.mark.parametrize(
    ("target", "status"),
    [
        ("browse", 0),
        ("browse/README.md", 0),
        ("missing", 3),
        ("https://github.com/octo/demo", 0),
        ("https://github.com/octo/demo/blob/main/docs/guide.md#L2", 0),
        ("https://github.com/octo/demo/pull/7/files", 0),
        ("https://github.com/octo/demo/commit/1a2b3c4", 0),
        # Refused, and sources other than GitHub's: still nothing started or fetched.
        ("https://github.com/octo/demo/issues/5", 3),
        ("https://example.com/octo/demo.git", 3),
        ("ssh://git@example.com/octo/demo.git", 3),
        ("ext::sh -c touch% pwned", 3),
    ],
)
def test_present_dry_run_loads_little_beyond_version(
    tmp_path: Path, target: str, status: int
) -> None:
    root = tmp_path / "browse"
    root.mkdir()
    (root / "README.md").write_text("# Local\n")
    local = target.startswith(("browse", "missing"))
    argument = str(tmp_path / target) if local else target
    baseline, _effects, _status = _loaded_and_effects("--version")

    loaded, effects, exit_status = _loaded_and_effects(
        argument, "--present", "--dry-run", "--format", "json"
    )

    assert exit_status == status
    allowed = _PRESENT_LOCAL_EXTRA | _PRESENT_STDLIB_EXTRA
    if not local:
        allowed |= _PRESENT_LINK_EXTRA
    assert sorted(_beyond(loaded, baseline) - allowed) == []
    assert effects == []
    assert not (tmp_path / "pwned").exists()
    if local:
        # A local target needs not even the Git tree source a URL's page is spelled with.
        assert _git_source_modules_in(loaded) == []


def test_plugin_cache_directory_is_owner_only_and_named_by_the_plugin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(cache))

    directory = plugin_api.plugin_cache_directory("agents")

    assert directory == cache / "plugins" / "agents"
    assert directory.is_dir()
    assert directory.stat().st_mode & 0o077 == 0
    # A second call verifies the directory it made instead of failing on it.
    assert plugin_api.plugin_cache_directory("agents") == directory


@pytest.mark.parametrize("name", ["", "../agents", "Agents", "a/b", "9agents"])
def test_plugin_cache_directory_refuses_a_name_that_is_not_a_plugin_name(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(tmp_path / "cache"))
    with pytest.raises(ValueError, match="not a plugin name"):
        plugin_api.plugin_cache_directory(name)
    assert not (tmp_path / "cache").exists()


def test_plugin_cache_directory_reports_an_unusable_root_without_its_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o777)
    shared.chmod(0o777)
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(shared))

    with pytest.raises(plugin_api.PluginCacheUnavailableError) as raised:
        plugin_api.plugin_cache_directory("agents")
    assert str(tmp_path) not in str(raised.value)


def test_a_plugin_cache_directory_does_not_block_the_repository_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``open_cache`` refuses a root holding unknown durable entries and no layout.

    A plugin may make its directory before anything acquires a repository, so the
    repository cache must still adopt that root.
    """
    from metabrowser.cache.layout import open_cache

    cache = tmp_path / "cache"
    monkeypatch.setenv("METABROWSER_CACHE_DIR", str(cache))
    monkeypatch.setenv("METABROWSER_CONFIG_DIR", str(tmp_path / "config"))
    plugin_api.plugin_cache_directory("agents")

    assert open_cache().home == cache


def test_the_jsonl_parse_limit_is_read_when_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    from metabrowser import jsonl_view

    monkeypatch.setattr(jsonl_view, "_JSONL_PARSE_MAX_BYTES", 64)
    assert plugin_api.jsonl_parse_max_bytes() == 64


def test_the_agents_sidekick_imports_only_the_public_plugin_api() -> None:
    """A built-in sidekick is held to the contract a third-party one gets."""
    import ast

    import metabrowser.builtin_plugins.agents.sidekick as sidekick

    tree = ast.parse(Path(sidekick.__file__).read_text(encoding="utf-8"))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("metabrowser")
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name.startswith("metabrowser")
    }
    assert imported == {"metabrowser.plugin_api"}
