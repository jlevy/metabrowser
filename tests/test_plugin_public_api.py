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
    # Acquiring a Git source and serving its pin.
    "metabrowser.cli.acquire_cli",
    "metabrowser.cli.git_pin_cli",
    "metabrowser.cli.selection",
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
