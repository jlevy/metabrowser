"""The platform requirements `docs/installation.md` states, held to the files that set them.

The values live in code: `requires-python` in `pyproject.toml`, `LSMinimumSystemVersion`
in the app's `Info.plist` with the `platforms` floor in `Package.swift`, the default
`ARCHES` (`default_arches` in `apps/macos/scripts/common.sh`), `swift-tools-version` in
`Package.swift`,
and the oldest Xcode the app's CI job selects. A user needs the figures themselves, so
the installation guide restates them, and this test is what lets it: a change to any
source fails here until the guide says the new value.
"""

from __future__ import annotations

import plistlib
import re
import tomllib
from pathlib import Path
from typing import NamedTuple

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
GUIDE = REPO_ROOT / "docs/installation.md"
PYPROJECT = REPO_ROOT / "pyproject.toml"
INFO_PLIST = REPO_ROOT / "apps/macos/Resources/Info.plist"
PACKAGE_SWIFT = REPO_ROOT / "apps/macos/Package.swift"
COMMON_SH = REPO_ROOT / "apps/macos/scripts/common.sh"
APP_WORKFLOW = REPO_ROOT / ".github/workflows/macos-app.yml"

# What the guide writes for each figure. A figure the guide states anywhere must be the
# one its source sets, so a stale second copy fails as well as a stale first.
_STATED = {
    "Python": re.compile(r"\bPython (\d+(?:\.\d+)*)"),
    "macOS": re.compile(r"\bmacOS (\d+(?:\.\d+)*)"),
    "Xcode": re.compile(r"\bXcode (\d+(?:\.\d+)*)"),
    "Swift": re.compile(r"\bSwift (\d+(?:\.\d+)*)"),
}
_APPLE_SILICON = "Apple silicon"


class Sources(NamedTuple):
    python: str
    macos: str
    xcode: str
    swift: str
    arches: tuple[str, ...]


def _display(version: str) -> str:
    """``26.0`` as a person writes it, ``26``; ``26.6`` unchanged."""

    return re.sub(r"(?:\.0)+$", "", version)


def _one(pattern: str, text: str, where: Path) -> str:
    match = re.search(pattern, text, re.MULTILINE)
    assert match, f"{where.relative_to(REPO_ROOT)} no longer matches {pattern!r}"
    return match.group(1)


def read_sources() -> Sources:
    requires = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["requires-python"]
    python = _one(r">=\s*(\d+(?:\.\d+)*)", requires, PYPROJECT)

    plist = plistlib.loads(INFO_PLIST.read_bytes())
    macos = _display(str(plist["LSMinimumSystemVersion"]))
    package = PACKAGE_SWIFT.read_text(encoding="utf-8")
    platform = _one(r"\.macOS\(\.v(\d+(?:_\d+)*)\)", package, PACKAGE_SWIFT).replace("_", ".")
    assert _display(platform) == macos, (
        f"Package.swift's platforms floor is macOS {platform} but Info.plist's "
        f"LSMinimumSystemVersion is {macos}; make them agree"
    )
    swift = _one(r"^// swift-tools-version:\s*(\d+(?:\.\d+)*)", package, PACKAGE_SWIFT)

    arches = _one(r'^default_arches="([^"]*)"$', COMMON_SH.read_text(encoding="utf-8"), COMMON_SH)

    workflow = yaml.safe_load(APP_WORKFLOW.read_text(encoding="utf-8"))
    included = workflow["jobs"]["app"]["strategy"]["matrix"]["include"]
    xcodes = [str(entry["xcode"]) for entry in included]
    xcode = min(xcodes, key=lambda version: tuple(int(part) for part in version.split(".")))

    return Sources(python, macos, xcode, swift, tuple(arches.split()))


def findings(guide: str, sources: Sources) -> list[str]:
    """What *guide* states that its sources do not set, or omits."""

    wanted = {
        "Python": sources.python,
        "macOS": sources.macos,
        "Xcode": sources.xcode,
        "Swift": sources.swift,
    }
    found: list[str] = []
    for name, pattern in _STATED.items():
        stated = pattern.findall(guide)
        if not stated:
            found.append(f"states no {name} version; its source sets {wanted[name]}")
        found += [
            f"states {name} {value} where its source sets {wanted[name]}"
            for value in stated
            if value != wanted[name]
        ]
    if sources.arches == ("arm64",):
        if _APPLE_SILICON not in guide:
            found.append(f"does not say the app is built for {_APPLE_SILICON}")
    else:
        found.append(
            f"the app is built for {' '.join(sources.arches)} by default; say which Macs the "
            "app runs on, then update this test"
        )
    return found


def test_installation_guide_states_the_requirements_the_code_sets() -> None:
    problems = findings(GUIDE.read_text(encoding="utf-8"), read_sources())
    assert not problems, "docs/installation.md " + "; ".join(problems)


def test_the_requirements_check_sees_what_it_must() -> None:
    sources = Sources("3.12", "26", "26.6", "6.3", ("arm64",))
    right = (
        "Python 3.12 or later. A Mac with Apple silicon, on macOS 26 or later. "
        "Xcode 26.6 or later, with Swift 6.3 or later."
    )
    assert findings(right, sources) == []
    stale = right.replace("Python 3.12", "Python 3.11").replace("Apple silicon", "a")
    assert findings(stale, sources) == [
        "states Python 3.11 where its source sets 3.12",
        "does not say the app is built for Apple silicon",
    ]
    assert findings(right + " Before macOS 15, ...", sources) == [
        "states macOS 15 where its source sets 26"
    ]
    assert findings(right, sources._replace(arches=("arm64", "x86_64")))
    assert _display("26.0") == "26"
    assert _display("26.6") == "26.6"
