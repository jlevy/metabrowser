"""KPress is Metabrowser's required, released rendering dependency."""

from __future__ import annotations

import tomllib
from pathlib import Path

PROJECT_FILE = Path(__file__).resolve().parent.parent / "pyproject.toml"
SOURCE_DIR = PROJECT_FILE.parent / "src" / "metabrowser"


def test_kpress_is_an_exact_required_runtime_dependency() -> None:
    project = tomllib.loads(PROJECT_FILE.read_text(encoding="utf-8"))

    assert "kpress==0.3.5" in project["project"]["dependencies"]
    assert "kpress" not in project["project"].get("optional-dependencies", {})
    assert "kpress" not in project.get("dependency-groups", {}).get("dev", [])


def test_the_pinned_kpress_release_is_the_one_reviewed_for_the_cool_off() -> None:
    """The pin and its supply-chain record move together.

    KPress is first-party and exempt from the cool-off, but the exemption is
    per-release: each one is reviewed against its predecessor. Bumping the pin
    without updating that record would leave the exemption naming a version
    nobody ships, which reads as reviewed when it is not.
    """

    project = tomllib.loads(PROJECT_FILE.read_text(encoding="utf-8"))
    pins = [d for d in project["project"]["dependencies"] if d.startswith("kpress")]
    assert len(pins) == 1, pins

    policy = (PROJECT_FILE.parent / "SUPPLY-CHAIN-SECURITY.md").read_text(encoding="utf-8")
    assert f"`{pins[0]}`" in policy, f"{pins[0]} is not recorded in SUPPLY-CHAIN-SECURITY.md"


def test_kpress_does_not_resolve_from_the_monorepo_workspace() -> None:
    project = tomllib.loads(PROJECT_FILE.read_text(encoding="utf-8"))

    assert "kpress" not in project.get("tool", {}).get("uv", {}).get("sources", {})


def test_the_install_guide_names_the_pinned_kpress_release() -> None:
    """A version in prose that nothing maintains goes stale, and this one did.

    ``docs/installation.md`` tells a reader which KPress the package pulls in,
    and warns them off installing a second one beside it. That sentence sat at
    0.3.3 through two upgrades because only the pin itself was checked. The
    dated research and plan documents deliberately keep the version they were
    written against and are not covered here -- they record what was verified at
    the time, not what ships now.
    """

    project = tomllib.loads(PROJECT_FILE.read_text(encoding="utf-8"))
    pins = [d for d in project["project"]["dependencies"] if d.startswith("kpress")]
    assert len(pins) == 1, pins

    guide = (PROJECT_FILE.parent / "docs" / "installation.md").read_text(encoding="utf-8")
    assert f"`{pins[0]}`" in guide, f"{pins[0]} is not named in docs/installation.md"


def test_the_toc_rail_is_reserved_through_kpress_not_reimplemented_in_host_css() -> None:
    """The reading column holds one position, and KPress is what holds it.

    Metabrowser briefly carried its own reserved-rail CSS because KPress had no
    option for it. KPress 0.3.1 does (``RenderOptions.toc_rail``), and the two
    implementations must never coexist: upstream reserves the rail by gridding
    the wide band and placing the prose in track 2, the host version used a left
    margin, and together they offset the column twice.
    """

    adapter = (SOURCE_DIR / "kpress_adapter.py").read_text(encoding="utf-8")
    styles = (SOURCE_DIR / "static" / "styles.css").read_text(encoding="utf-8")

    assert 'toc_rail="reserved"' in adapter

    # The host reimplementation and every token it needed are gone for good.
    for residue in (
        "Reserved TOC rail",
        "--embedded-toc-rail-width",
        "--embedded-doc-column-width",
        ":not(:has(.kpress-toc))",
    ):
        assert residue not in styles, (
            f"{residue!r} is host CSS reimplementing KPress's reserved rail; "
            'pass toc_rail="reserved" instead and delete it'
        )


def test_runtime_has_no_optional_kpress_branch() -> None:
    adapter = (SOURCE_DIR / "kpress_adapter.py").read_text(encoding="utf-8")
    server = (SOURCE_DIR / "server.py").read_text(encoding="utf-8")

    assert "KPressUnavailableError" not in adapter
    assert "KPressUnavailableError" not in server
    assert "kpress_unavailable" not in server
