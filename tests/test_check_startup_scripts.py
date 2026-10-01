"""The startup-script budget check: what it counts, and that it bites.

``devtools/check_startup_scripts.py`` computes on every ``make lint-check`` the number
the performance loop's gate reads from a browser. These tests hold the three things that
would make that number wrong without failing anything: the list of scripts it counts,
the size it gives each, and the ceilings it compares them with.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from devtools import check_startup_scripts as check
from metabrowser import server


def test_the_shell_fits_the_budget() -> None:
    scripts = check.measure(check.render_folder_shell())
    assert check.problems(scripts, check.load_limits()) == []
    assert check.main() == 0


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
    report = capsys.readouterr().err
    assert f"the budget is {measured - 1} KB" in report
    assert f"the budget is {len(scripts) - 1}" in report
    # The largest script leads the list a reader works down.
    largest = max(scripts, key=lambda script: script.transfer_bytes)
    assert report.index(largest.url_path) == min(
        report.index(script.url_path) for script in scripts
    )


def test_a_script_added_to_the_shell_is_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    # git-panel.js is an on-demand script. As one more startup script it is what the
    # budget exists to refuse: with it the shell is over.
    html = check.render_folder_shell()
    before = check.measure(html)
    added = html.replace(
        '<script src="/static/app.js',
        '<script src="/static/git-panel.js"></script><script src="/static/app.js',
        1,
    )
    after = check.measure(added)

    assert [script.url_path for script in after if script not in before] == ["/static/git-panel.js"]
    assert len(after) == len(before) + 1
    assert check.problems(before, check.load_limits()) == []
    over = check.problems(after, check.load_limits())
    assert len(over) == 1 and over[0].startswith("startup_script_transfer_kb:")


def test_only_what_blocks_the_parser_counts() -> None:
    html = (
        '<script src="/static/app.js?v=1"></script>'
        '<script async src="/static/perf.js"></script>'
        '<script defer src="/static/icons.js"></script>'
        '<script type="module" src="/static/navigation.js"></script>'
        '<script src="/static/vendor/highlight.min.js"></script>'
        "<script>window.inline = 1;</script>"
        '<link rel="stylesheet" href="/static/styles.css">'
    )
    assert check.startup_script_paths(html) == ["/static/app.js"]


def test_the_computed_size_is_the_body_the_application_sends() -> None:
    # The check compresses each file itself. That is the gate's number only while it is
    # what the running application sends, gzip middleware and all.
    client = TestClient(server.app, base_url="http://127.0.0.1")
    scripts = check.measure(check.render_folder_shell())
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


def test_the_gate_rounds_as_the_probe_does() -> None:
    def at(total: int) -> list[check.StartupScript]:
        return [check.StartupScript("/static/app.js", total, total)]

    # probe.js: Math.round(bytes / 1024). Half a kibibyte rounds up.
    assert check.transfer_kb(at(175 * 1024 + 511)) == 175
    assert check.transfer_kb(at(175 * 1024 + 512)) == 176
    probe = (check.ROOT / "explorations" / "performance-loop" / "probe.js").read_text(
        encoding="utf-8"
    )
    assert "Math.round(list.reduce((total, r) => total + (r.transferSize || 0), 0) / 1024)" in probe
    assert (
        '!r.name.includes("/static/vendor/") && r.startTime < Number(nav.domContentLoadedEventEnd)'
        in probe
    )


def test_lint_check_runs_it() -> None:
    # The budget was crossed unnoticed because only a browser capture applied it. It
    # holds only while the gate every change passes through runs this check.
    makefile = (check.ROOT / "Makefile").read_text(encoding="utf-8")
    lint_check = makefile[makefile.index("\nlint-check:") :]
    lint_check = lint_check[: lint_check.index("\n\n")]
    assert "$(UV_RUN) python -m devtools.check_startup_scripts" in lint_check
