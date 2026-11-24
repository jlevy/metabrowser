"""Production PDF-preview registration, the actions each host and profile gets, and lifecycle.

The full output is pinned by ``tests/golden/cli-ui-pdf-preview.tryscript.md``; this test
names the decisions a reader of the plan's actions table would check first.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from tests.required_tools import require_node

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_JS = Path(__file__).resolve().parent / "dom" / "pdf-preview-session.js"
PLUGIN_ROOT = REPO_ROOT / "src" / "metabrowser" / "builtin_plugins" / "pdf"
RAW = "/raw?path=papers%2F%3Cunsafe%20%22quoted%22%20%26%20file%3E.pdf"


def _session() -> dict[str, Any]:
    require_node()
    result = subprocess.run(
        ["node", str(SESSION_JS)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, (
        f"PDF preview session failed:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    session: dict[str, Any] = json.loads(result.stdout)
    return session


def _labels(mount: dict[str, Any]) -> list[str]:
    return [action["text"] for action in mount["actions"]]


def test_each_host_and_profile_gets_its_viewer_and_actions() -> None:
    matrix = _session()["matrix"]
    assert {label: _labels(mount) for label, mount in matrix.items()} == {
        "appActive": ["Open", "Download"],
        "appInert": ["Open", "Download"],
        "browserActive": ["Download", "Open in new tab"],
        "browserInert": ["Download", "Open in new tab"],
    }
    # The viewer does not depend on trust: every page's policy admits `/raw` objects.
    assert {label: mount["body"]["tag"] for label, mount in matrix.items()} == {
        "appActive": "embed",
        "appInert": "embed",
        "browserActive": "embed",
        "browserInert": "embed",
    }
    viewer = matrix["browserActive"]["body"]["attributes"]
    assert viewer["type"] == "application/pdf"
    assert viewer["src"] == RAW
    for mount in matrix.values():
        assert all(action["attributes"]["href"] == RAW for action in mount["actions"])


def test_only_the_apps_open_link_carries_the_marker_and_its_subject() -> None:
    session = _session()
    open_link = session["matrix"]["appActive"]["actions"][0]["attributes"]
    assert open_link["data-metabrowser-open-file"] == "filesystem"
    assert open_link["download"] == '<unsafe "quoted" & file>.pdf'
    for label in ("browserActive", "browserInert"):
        for action in session["matrix"][label]["actions"]:
            assert "data-metabrowser-open-file" not in action["attributes"]
    pinned = session["pinned"]["app"]["actions"][0]["attributes"]
    assert pinned["data-metabrowser-open-file"] == "git_revision"
    assert pinned["download"] == "report.pdf"
    assert pinned["href"] == "/raw?path=g1-cGFwZXJz%2Fg1-cmVwb3J0LnBkZg"


def test_the_sdk_reads_the_host_and_profile_conservatively() -> None:
    accessors = _session()["sdkAccessors"]
    assert accessors["host"] == {
        "app": {"actions": ["open-file"], "openFile": True},
        "browser": {"actions": [], "openFile": False},
        "malformed": {"actions": [], "openFile": False},
        "mixed": {"actions": ["reveal-file"], "openFile": False},
    }
    capabilities = accessors["capabilities"]
    assert capabilities["missing"] == {"activeContent": False, "mutations": False}
    assert capabilities["inert"] == {"activeContent": False, "mutations": False}
    assert capabilities["active"] == {"activeContent": True, "mutations": False}
    assert capabilities["frozen"] is True


def test_the_renderer_loads_lazily_and_disposes() -> None:
    session = _session()
    assert session["composition"] == {"assetRequests": ["pdf"], "initialView": "preview"}
    assert session["innerHtmlWrites"] == 0
    assert session["replacement"] == {
        "firstDetached": True,
        "firstReleasedSrc": True,
        "hostHoldsOne": True,
    }
    assert session["disposal"] == {"emptied": True}
    assert session["emptyPathError"] == "pdf preview requires a non-empty string path"


def test_pdf_styles_and_rendering_are_plugin_owned() -> None:
    core_app = (REPO_ROOT / "src/metabrowser/static/app.js").read_text(encoding="utf-8")
    core_css = (REPO_ROOT / "src/metabrowser/static/styles.css").read_text(encoding="utf-8")
    plugin_css = PLUGIN_ROOT.joinpath("styles.css").read_text(encoding="utf-8")
    assert "pdf-viewer" not in core_app
    assert ".pdf-viewer" not in core_css
    assert ".metabrowser-pdf-host .pdf-viewer" in plugin_css
