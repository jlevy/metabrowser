"""Shared plugin-directory configuration for MetaBrowser CLI commands."""

from __future__ import annotations

import os
from pathlib import Path

from metabrowser.dotenv import load_dotenv_chain
from metabrowser.errors import CLIError
from metabrowser.plugin_paths import normalize_plugin_dirs


def resolve_extra_plugin_dirs(plugins_dir: list[Path] | None) -> list[Path]:
    """Load, normalize, validate, and deduplicate configured plugin directories.

    Environment directories come before CLI directories. All paths are expanded
    and resolved so every command hands discovery the same canonical values.
    """
    load_dotenv_chain()
    env_value = os.environ.get("METABROWSER_PLUGINS_DIRS", "")
    env_paths = [Path(path) for path in env_value.split(os.pathsep) if path]
    cli_paths = list(plugins_dir or [])

    try:
        return normalize_plugin_dirs([*env_paths, *cli_paths])
    except ValueError as exc:
        raise CLIError(str(exc)) from exc
