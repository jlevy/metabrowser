"""Tests for the golden session schema: what is normalized and what is kept."""

from __future__ import annotations

from pathlib import Path

from metabrowser.normalize import (
    CURSOR_PLACEHOLDER,
    HOME_PLACEHOLDER,
    MTIME_PLACEHOLDER,
    ROOT_PLACEHOLDER,
    NormalizeContext,
    describe_schema,
    normalize_payload,
    normalize_text,
)

ROOT = Path("/tmp/sandbox/checkroot")
HOME = Path("/tmp/sandbox/home")


def _ctx(**kwargs: object) -> NormalizeContext:
    return NormalizeContext(root=ROOT, home=HOME, **kwargs)  # type: ignore[arg-type]


def test_absolute_root_path_becomes_a_placeholder() -> None:
    payload = {"root": str(ROOT)}

    assert normalize_payload(payload, _ctx()) == {"root": ROOT_PLACEHOLDER}


def test_path_under_root_keeps_its_suffix() -> None:
    payload = {"root": f"{ROOT}/docs/guide.md"}

    assert normalize_payload(payload, _ctx()) == {"root": f"{ROOT_PLACEHOLDER}/docs/guide.md"}


def test_application_home_normalizes_independently_of_root() -> None:
    payload = {"home": str(HOME / "cache" / "layout.yml")}

    normalized = normalize_payload(payload, _ctx())

    assert normalized == {"home": f"{HOME_PLACEHOLDER}/cache/layout.yml"}


def test_nested_structures_are_normalized_throughout() -> None:
    payload = {"tree": [{"path": str(ROOT / "a.md")}, {"path": str(ROOT / "b.md")}]}

    normalized = normalize_payload(payload, _ctx())

    assert normalized == {
        "tree": [
            {"path": f"{ROOT_PLACEHOLDER}/a.md"},
            {"path": f"{ROOT_PLACEHOLDER}/b.md"},
        ]
    }


def test_git_revisions_are_kept_because_fixtures_pin_them() -> None:
    """Fixture repositories build deterministically, so a revision is real coverage."""

    revision = "1e9bc884891152dfb4e0ac2d87c40f5a5b7389a9"
    payload = {"head": {"revision": revision}}

    assert normalize_payload(payload, _ctx()) == payload


def test_mtime_is_kept_by_default_because_fixtures_pin_it() -> None:
    payload = {"mtime": 1699999999.0, "mtime_hash": "abc123"}

    assert normalize_payload(payload, _ctx()) == payload


def test_mtime_is_normalized_when_the_fixture_cannot_pin_it() -> None:
    payload = {"mtime": 1699999999.0, "mtime_hash": "abc123"}

    normalized = normalize_payload(payload, _ctx(normalize_mtimes=True))

    assert normalized == {"mtime": MTIME_PLACEHOLDER, "mtime_hash": MTIME_PLACEHOLDER}


def test_a_payload_of_every_unstable_field_normalizes_to_none_of_them() -> None:
    """The round-trip the golden guidelines ask for."""

    payload = {
        "root": str(ROOT),
        "home": str(HOME),
        "mtime": 1699999999.0,
        "nested": {"path": str(ROOT / "x"), "list": [str(HOME / "y")]},
    }

    rendered = repr(normalize_payload(payload, _ctx(normalize_mtimes=True)))

    assert str(ROOT) not in rendered
    assert str(HOME) not in rendered
    assert "1699999999" not in rendered


def test_text_normalization_covers_console_output() -> None:
    text = f"walking {ROOT}/docs\ncache at {HOME}/cache\n"

    normalized = normalize_text(text, _ctx())

    assert normalized == f"walking {ROOT_PLACEHOLDER}/docs\ncache at {HOME_PLACEHOLDER}/cache\n"


def test_home_inside_root_still_normalizes_to_the_more_specific_prefix() -> None:
    """Longest prefix wins, so a home under the served root is not mislabeled."""

    root = Path("/tmp/sandbox")
    home = Path("/tmp/sandbox/home")
    ctx = NormalizeContext(root=root, home=home)

    normalized = normalize_payload({"p": str(home / "config.yml")}, ctx)

    assert normalized == {"p": f"{HOME_PLACEHOLDER}/config.yml"}


def test_schema_is_documented_for_every_rule_it_applies() -> None:
    described = describe_schema()

    for token in (ROOT_PLACEHOLDER, HOME_PLACEHOLDER, MTIME_PLACEHOLDER):
        assert token in described


def test_a_pagination_cursor_is_always_normalized() -> None:
    """It carries a random session token, so no fixture arrangement pins it."""

    payload = {"page_cursor": "eyJzIjoiUUJNUzYzTl9QTnI1QWVxVnplQWVYTjNaIn0="}

    assert normalize_payload(payload, _ctx()) == {"page_cursor": CURSOR_PLACEHOLDER}


def test_an_absent_cursor_is_left_alone() -> None:
    assert normalize_payload({"page_cursor": None}, _ctx()) == {"page_cursor": None}
