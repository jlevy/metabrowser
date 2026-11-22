"""``magic`` kind rules: a binary format claimed by the bytes it starts with.

A magic rule matches only where a file would otherwise be ``binary``, whatever its name,
on the bytes on disk; ``ext`` or ``exts`` beside it decide only the tree's chevron. The
classification sites are pinned end to end by ``tests/golden/cli-api-sqlite.tryscript.md``
(a served folder) and ``tests/test_sqlite_pin.py`` (a Git pin).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from metabrowser.file_kinds import FileContext
from metabrowser.plugin_loader.classify import (
    CompiledKindRule,
    build_classifier,
    classify_identity,
    classify_magic,
)
from metabrowser.plugin_loader.manifest import MAGIC_MAX_END, KindRule, PluginManifest

SQLITE_HEX = b"SQLite format 3\x00".hex()


def _manifest(match: dict[str, Any]) -> PluginManifest:
    return PluginManifest.model_validate(
        {
            "plugin": {"name": "probe", "version": "0.0.1", "sdk_version": "0.8"},
            "kind": [{"id": "probe", "match": match}],
        }
    )


def _rules(*rules: tuple[str, dict[str, Any], int]) -> list[CompiledKindRule]:
    return [
        CompiledKindRule(
            rule=KindRule.model_validate({"id": kind, "match": match, "priority": priority}),
            plugin_name=kind,
            discovery_index=index,
        )
        for index, (kind, match, priority) in enumerate(rules)
    ]


def test_a_magic_rule_matches_its_bytes_whatever_the_name() -> None:
    rules = _rules(("sqlite", {"magic": {"hex": SQLITE_HEX}, "exts": [".db"]}, 0))
    header = b"SQLite format 3\x00" + bytes(84)
    assert classify_magic(rules, header) == "sqlite"
    assert classify_magic(rules, b"not a database") is None
    assert classify_magic(rules, b"SQLite") is None


def test_a_magic_rule_never_matches_by_its_extensions() -> None:
    rules = _rules(("sqlite", {"magic": {"hex": SQLITE_HEX}, "exts": [".db"]}, 0))
    classify = build_classifier(rules)
    assert classify(FileContext(Path("/nowhere/app.db"), ".db")) is None
    assert classify_identity(rules, ext=".db", basename="app.db") is None


def test_priority_then_discovery_order_decides_between_magic_rules() -> None:
    rules = _rules(
        ("first", {"magic": {"hex": "53"}}, 0),
        ("narrow", {"magic": {"offset": 1, "hex": "51"}}, 100),
        ("second", {"magic": {"hex": "53"}}, 0),
    )
    assert classify_magic(rules, b"SQL") == "narrow"
    assert classify_magic(rules, b"SX") == "first"


def test_magic_hex_is_validated() -> None:
    with pytest.raises(ValidationError, match="not hexadecimal"):
        _manifest({"magic": {"hex": "zz"}})
    with pytest.raises(ValidationError, match="names no bytes"):
        _manifest({"magic": {"hex": ""}})
    with pytest.raises(ValidationError):
        _manifest({"magic": {"offset": -1, "hex": "00"}})


@pytest.mark.parametrize(
    ("match", "problem"),
    [
        ({"magic": {"hex": "00", "offset": MAGIC_MAX_END}}, "ends past byte"),
        ({"magic": {"hex": SQLITE_HEX}, "basename": "History"}, "takes only ext or exts"),
        ({"magic": {"hex": SQLITE_HEX}, "json_has_key": "x"}, "takes only ext or exts"),
    ],
)
def test_a_magic_rule_is_checked_for_consistency(match: dict[str, Any], problem: str) -> None:
    problems = _manifest(match).validate_consistency()
    assert any(problem in line for line in problems), problems


def test_the_sqlite_manifest_declares_one_consistent_magic_rule() -> None:
    from metabrowser.plugin_loader.manifest import load_manifest

    path = Path(__file__).parent.parent / "src/metabrowser/builtin_plugins/sqlite/manifest.toml"
    manifest = load_manifest(path)
    assert manifest.validate_consistency() == []
    [rule] = manifest.kind
    assert rule.match.magic is not None
    assert rule.match.magic.expected == b"SQLite format 3\x00"
