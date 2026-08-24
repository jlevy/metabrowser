from __future__ import annotations

from pathlib import Path

from devtools.source_naming import find_source_naming_findings


def test_source_filename_rule_covers_javascript_and_typescript_modules() -> None:
    paths = (
        Path("good-name.js"),
        Path("types.d.ts"),
        Path("bad_name.tsx"),
        Path("BadName.mjs"),
        Path("src/metabrowser/static/vendor/upstream_bundle.js"),
    )

    assert find_source_naming_findings(paths) == [
        "BadName.mjs: JavaScript and TypeScript filenames must use lowercase kebab-case",
        "bad_name.tsx: JavaScript and TypeScript filenames must use lowercase kebab-case",
    ]


def test_repository_source_filenames_follow_the_convention() -> None:
    assert find_source_naming_findings() == []
