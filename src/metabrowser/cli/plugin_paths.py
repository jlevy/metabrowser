"""Shared plugin-directory configuration for MetaBrowser CLI commands."""

from __future__ import annotations

import os
from pathlib import Path

from metabrowser.dotenv import load_dotenv_chain
from metabrowser.errors import CLIError


def resolve_extra_plugin_dirs(plugins_dir: list[Path] | None) -> list[Path]:
    """Load, normalize, validate, and deduplicate configured plugin directories.

    Environment directories come before CLI directories. All paths are expanded
    and resolved so every command hands discovery the same canonical values.
    """
    load_dotenv_chain()
    env_value = os.environ.get("METABROWSER_PLUGINS_DIRS", "")
    env_paths = [Path(path) for path in env_value.split(os.pathsep) if path]
    cli_paths = list(plugins_dir or [])

    seen: set[str] = set()
    resolved_paths: list[Path] = []
    for path in [*env_paths, *cli_paths]:
        resolved = path.expanduser().resolve()
        if not resolved.is_dir():
            raise CLIError(f"plugin directory not a directory: {path}")
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        resolved_paths.append(resolved)
    return resolved_paths
