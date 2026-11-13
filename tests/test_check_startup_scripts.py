"""The startup-script budget check: what it counts, and that it bites.

``devtools/check_startup_scripts.py`` computes on every ``make lint-check`` the number
the performance loop's gate reads from a browser. These tests hold the things that
would make that number wrong without failing anything: the scripts it counts, the ones
a script asks for that no tag shows, the size it gives each, and the ceilings it
compares them with.
"""

from __future__ import annotations

import json
import subprocess
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import pytest
from starlette.testclient import TestClient

from devtools import check_startup_scripts as check
from metabrowser import server
from tests.required_tools import needs_node, require_node

pytestmark = needs_node


def _tag_before_app(html: str, tag: str) -> str:
    """*html* with *tag* written ahead of the shell's last startup script."""

    assert html.count('<script src="/static/app.js') == 1
    return html.replace('<script src="/static/app.js', tag + '<script src="/static/app.js', 1)


def _block_after_app(html: str, block: str) -> str:
    """*html* with an inline script after the shell's last startup script."""

    head, tag, rest = html.partition('<script src="/static/app.js')
    close = rest.index("</script>") + len("</script>")
    return head + tag + rest[:close] + block + rest[close:]


def test_the_shell_fits_the_budget(capsys: pytest.CaptureFixture[str]) -> None:
    assert check.main() == 0
    summary = capsys.readouterr().out.splitlines()
    assert summary[0].startswith("startup scripts: ")
    assert " under the budget)" in summary[0]
    # The two shells with a script more are reported beside the same budget, by name.
    assert summary[1].startswith("  a pull-request address adds pull-route.js: ")
    assert summary[2].startswith("  a pinned revision adds git-path.js: ")
    assert all(line.endswith("not gated)") for line in summary[1:])


def test_the_shell_is_rendered_for_a_folder_whatever_the_process_served(
    tmp_path: Path,
) -> None:
    # The check renders through the application for a folder of its own. A source the
    # process was serving before, here a folder with a file in it, changes nothing.
    (tmp_path / "notes.md").write_text("# Notes\n", encoding="utf-8")
    server._set_root_dir(tmp_path)  # pyright: ignore[reportPrivateUsage]
    after_another_source = check.startup_script_paths(check.render_folder_shell())
    assert after_another_source == check.startup_script_paths(check.render_folder_shell())
    assert "/static/app.js" in after_another_source
    assert "/static/git-path.js" not in after_another_source


def test_a_pull_request_address_has_its_routes_as_a_startup_script() -> None:
    # The server knows the address when it renders, so the page's routes arrive with
    # the shell and not a round trip after it. A folder's other pages never get them.
    folder_html, pull_html = check.render_shells(check.FOLDER_ADDRESS, check.PULL_ADDRESS)
    folder = check.startup_script_paths(folder_html)
    pull = check.startup_script_paths(pull_html)
    added = [f"/static/{name}" for name in server.PULL_PAGE_STARTUP_SCRIPTS]
    assert added == ["/static/pull-route.js"]
    assert sorted(pull) == sorted(folder + added)
    assert not set(added) & set(folder)
    # And nothing on either page asks for a script itself before the first tree.
    assert check.script_requests(folder_html, check.FOLDER_ADDRESS) == []
    assert check.script_requests(pull_html, check.PULL_ADDRESS) == []


def test_the_ceilings_are_the_budget_files() -> None:
    budgets = tomllib.loads(check.BUDGETS.read_text(encoding="utf-8"))["metrics"]
    limits = check.load_limits()
    assert limits.requests == budgets["startup_script_requests"]["maximum"]
    assert limits.transfer_kb == budgets["startup_script_transfer_kb"]["maximum"]
    # Both are gates in the file: a ceiling demoted to a target is no longer one.
    assert budgets["startup_script_requests"]["policy"] == "gate"
    assert budgets["startup_script_transfer_kb"]["policy"] == "gate"


def test_a_lower_ceiling_fails_and_names_the_scripts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    scripts = check.measure(check.render_folder_shell())
    measured = check.transfer_kb(scripts)
    budgets = tmp_path / "budgets.toml"
    budgets.write_text(
        f"[metrics.startup_script_requests]\nmaximum = {len(scripts) - 1}\n"
        f"[metrics.startup_script_transfer_kb]\nmaximum = {measured - 1}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check, "BUDGETS", budgets)

    assert check.main() == 1
    captured = capsys.readouterr()
    report = captured.err
    assert f"the budget is {measured - 1} KB" in report
    assert f"the budget is {len(scripts) - 1}" in report
    assert "bytes over)" in report
    assert " over the budget)" in captured.out.splitlines()[0]
    # The largest script leads the list a reader works down.
    largest = max(scripts, key=lambda script: script.transfer_bytes)
    assert report.index(largest.url_path) == min(
        report.index(script.url_path) for script in scripts
    )


@pytest.mark.parametrize("attribute", ["", " defer", " async"], ids=["blocking", "defer", "async"])
def test_a_script_added_to_the_shell_is_counted_whatever_its_attributes(attribute: str) -> None:
    # git-panel.js is an on-demand script. As one more startup script it is what the
    # budget exists to refuse: with it the shell is over. A deferred or async script
    # is requested as the parser meets it, the same as a blocking one.
    html = check.render_folder_shell()
    before = check.measure(html)
    after = check.measure(
        _tag_before_app(html, f'<script{attribute} src="/static/git-panel.js"></script>')
    )

    assert [script.url_path for script in after if script not in before] == ["/static/git-panel.js"]
    assert len(after) == len(before) + 1
    assert check.problems(before, check.load_limits()) == []
    over = check.problems(after, check.load_limits())
    assert len(over) == 1 and over[0].startswith("startup_script_transfer_kb:")


def test_what_the_probe_leaves_out_is_left_out() -> None:
    html = (
        '<script src="/static/app.js?v=1"></script>'
        '<script src="/static/vendor/highlight.min.js"></script>'
        "<script>window.inline = 1;</script>"
        '<link rel="stylesheet" href="/static/styles.css">'
    )
    assert check.startup_script_paths(html) == ["/static/app.js"]


def test_a_module_script_stops_the_check() -> None:
    # What a module imports is requested before DOMContentLoaded too, and no reading
    # of the HTML shows it. The check says it cannot count that; it does not guess.
    html = _tag_before_app(
        check.render_folder_shell(), '<script type="module" src="/static/navigation.js"></script>'
    )
    with pytest.raises(SystemExit, match="module script") as stopped:
        check.measure(html)
    assert "/static/navigation.js" in str(stopped.value)


@pytest.mark.parametrize(
    ("block", "requested"),
    [
        # A script that asks the asset loader for a bundle as it runs.
        (
            '<script>window.MetabrowserAssets.ensureAsset("pull-route");</script>',
            ("script", "/static/pull-route.js"),
        ),
        # One that waits for DOMContentLoaded and asks then: still before it ends.
        (
            '<script>document.addEventListener("DOMContentLoaded", () => {'
            ' window.MetabrowserAssets.ensureAsset("sdk-views"); });</script>',
            ("script", "/static/plugin-sdk-views.js"),
        ),
        # One that appends the element itself, and one that only preloads.
        (
            '<script>var s = document.createElement("script");'
            ' s.src = "/static/git-panel.js"; document.head.appendChild(s);</script>',
            ("script", "/static/git-panel.js"),
        ),
        (
            '<script>var l = document.createElement("link");'
            ' l.setAttribute("rel", "modulepreload");'
            ' l.setAttribute("href", "/plugin-static/text/index.js");'
            " document.head.append(l);</script>",
            ("link rel=modulepreload", "/plugin-static/text/index.js"),
        ),
        ('<script>import("/plugin-static/text/index.js");</script>', None),
    ],
    ids=["asset-loader", "on-DOMContentLoaded", "appended-script", "preload", "import"],
)
def test_a_script_that_asks_for_a_script_at_startup_fails_the_check(
    block: str, requested: tuple[str, str] | None
) -> None:
    # No tag shows these requests and the gate counts every one of them. The session
    # runs the shell's own scripts and reports each; the check refuses it by name.
    html = check.render_folder_shell()
    scripts = check.measure(html)
    assert check.script_requests(html, check.FOLDER_ADDRESS) == []

    asked = check.script_requests(_block_after_app(html, block), check.FOLDER_ADDRESS)

    expected = requested or ("import()", "/plugin-static/text/index.js")
    assert [(request.how, request.url_path) for request in asked] == [expected]
    found = check.problems(scripts, check.load_limits(), {check.FOLDER_ADDRESS: asked})
    assert len(found) == 1
    assert f"at /view/ requests {expected[1]} ({expected[0]})" in found[0]


def test_a_shell_whose_scripts_throw_stops_the_check() -> None:
    # A page whose startup failed tells nothing about what it requests.
    html = _block_after_app(check.render_folder_shell(), "<script>startup.broke();</script>")
    with pytest.raises(SystemExit, match="did not run in the startup session") as stopped:
        check.script_requests(html, check.FOLDER_ADDRESS)
    assert "ReferenceError: startup is not defined" in str(stopped.value)


def test_the_computed_size_is_the_body_the_application_sends() -> None:
    # The check compresses each file itself. That is the gate's number only while it is
    # what the running application sends, gzip middleware and all.
    scripts = check.measure(check.render_folder_shell())
    client = TestClient(server.app, base_url="http://127.0.0.1")
    assert len(scripts) > 10
    for script in scripts:
        response = client.get(script.url_path, headers={"Accept-Encoding": "gzip"})
        assert response.status_code == 200, script.url_path
        assert response.headers.get("content-encoding") == "gzip", script.url_path
        assert (
            response.num_bytes_downloaded
            == script.transfer_bytes - check.RESOURCE_TIMING_HEADER_BYTES
        ), script.url_path
        assert len(response.content) == script.decoded_bytes, script.url_path


# The probe's own selection and rounding, run on Resource Timing entries: the functions
# probe.js defines ahead of its body, which is what a browser capture evaluates.
_PROBE_ARITHMETIC = """
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const sandbox = { URL };
vm.createContext(sandbox);
vm.runInContext(source.slice(0, source.indexOf("\\n(async () =>")), sandbox);
const { entries, domContentLoadedEventEnd } = JSON.parse(process.argv[2]);
const counted = sandbox.startupScriptResources(entries, domContentLoadedEventEnd);
process.stdout.write(JSON.stringify({
  names: counted.map((entry) => entry.name),
  kb: sandbox.transferKb(counted),
}));
"""


def _probe(entries: Sequence[Mapping[str, object]]) -> dict[str, Any]:
    probe = check.ROOT / "explorations" / "performance-loop" / "probe.js"
    result = subprocess.run(
        [
            require_node(),
            "-e",
            _PROBE_ARITHMETIC,
            str(probe),
            json.dumps({"entries": entries, "domContentLoadedEventEnd": 100}),
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=20,
    )
    return cast("dict[str, Any]", json.loads(result.stdout))


def test_the_probe_counts_and_rounds_what_the_check_does() -> None:
    scripts = check.measure(check.render_folder_shell())
    origin = "http://127.0.0.1:8000"
    counted = [
        {
            "name": f"{origin}{script.url_path}?v=1",
            "startTime": 5,
            "transferSize": script.transfer_bytes,
        }
        for script in scripts
    ]
    # What the gate leaves out, in a browser's own entries: a vendored library, a
    # script that started after DOMContentLoaded, and anything that is not a script.
    others = [
        {"name": f"{origin}/static/vendor/highlight.min.js", "startTime": 5, "transferSize": 41444},
        {"name": f"{origin}/static/known-file-catalog.js", "startTime": 100, "transferSize": 13470},
        {"name": f"{origin}/static/styles.css", "startTime": 5, "transferSize": 30000},
        {"name": f"{origin}/api/tree", "startTime": 5, "transferSize": 900},
    ]

    probe = _probe(counted + others)

    assert probe["names"] == [entry["name"] for entry in counted]
    assert probe["kb"] == check.transfer_kb(scripts)


@pytest.mark.parametrize("total", [175 * 1024 + 511, 175 * 1024 + 512, 1, 0])
def test_the_check_rounds_half_a_kibibyte_as_the_probe_does(total: int) -> None:
    script = check.StartupScript("/static/app.js", total, total)
    entry = {"name": "http://127.0.0.1:8000/static/app.js", "startTime": 5, "transferSize": total}
    assert _probe([entry])["kb"] == check.transfer_kb([script])
    # The ceiling in bytes is the last total the gate still reports as its kilobytes.
    limits = check.Limits(requests=25, transfer_kb=175)
    assert check.transfer_kb([check.StartupScript("a", 0, limits.transfer_bytes)]) == 175
    assert check.transfer_kb([check.StartupScript("a", 0, limits.transfer_bytes + 1)]) == 176


def test_lint_check_runs_it() -> None:
    # The budget was crossed unnoticed because only a browser capture applied it. It
    # holds only while the gate every change passes through runs this check: this asks
    # make what `lint-check` would run.
    planned = subprocess.run(
        ["make", "--dry-run", "lint-check"],
        cwd=check.ROOT,
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    )
    assert any(
        line.rstrip().endswith("python -m devtools.check_startup_scripts")
        for line in planned.stdout.splitlines()
    )
