"""Public Python helpers used by installed plugin sidekicks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import metabrowser
import metabrowser.plugin_api as plugin_api
from metabrowser import (
    ArtifactCompressionError,
    ArtifactContractSpec,
    ArtifactDecompressionLimitError,
    ArtifactDecompressionTimeoutError,
    ArtifactPath,
    ArtifactValidationContext,
    BrowserParserSpec,
    CapabilitySet,
    CollectionPaginationPolicy,
    ConformanceCorpusSpec,
    JsonlParseLimitError,
    ResourceCollectionSpec,
    ResourceProfileSpec,
    ResourceTargetClass,
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
    "ArtifactContractSpec",
    "ArtifactValidationContext",
    "ArtifactCompressionError",
    "ArtifactDecompressionLimitError",
    "ArtifactDecompressionTimeoutError",
    "ArtifactPath",
    "BrowserParserSpec",
    "CapabilitySet",
    "CollectionPaginationPolicy",
    "ConformanceCorpusSpec",
    "JsonlParseLimitError",
    "LogEvent",
    "LogParser",
    "ResourceCollectionSpec",
    "ResourceProfileSpec",
    "ResourceTargetClass",
    "detect_adapter",
    "extract_agent_charts_cached",
    "register_log_adapter",
    "register_root_callback",
    "relativize_path",
    "resolve_directory",
    "resolve_path",
    "served_root",
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


def test_installed_capability_declaration_types_are_public() -> None:
    assert ArtifactContractSpec.__module__ == "metabrowser.plugin_loader.capability_types"
    assert ArtifactValidationContext.__module__ == "metabrowser.plugin_loader.capability_types"
    assert BrowserParserSpec.__module__ == "metabrowser.plugin_loader.capability_types"
    assert CapabilitySet.__module__ == "metabrowser.plugin_loader.capability_types"
    assert ConformanceCorpusSpec.__module__ == "metabrowser.plugin_loader.capability_types"
    assert CollectionPaginationPolicy.__module__ == "metabrowser.provider_resources.profiles"
    assert ResourceCollectionSpec.__module__ == "metabrowser.provider_resources.profiles"
    assert ResourceProfileSpec.__module__ == "metabrowser.provider_resources.profiles"
    assert ResourceTargetClass.__module__ == "metabrowser.provider_resources.profiles"
    assert "browser_consumed" in ArtifactContractSpec.__dataclass_fields__


def test_public_import_does_not_load_capability_registry_dependencies() -> None:
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


def test_version_command_does_not_load_capability_registry_dependencies() -> None:
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
