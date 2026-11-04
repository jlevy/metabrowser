"""Golden CLI transcript: a checkout's pull requests, read and refreshed by a folder's server.

Each command runs the production CLI in-process on a checkout served as a folder, as
``metab <checkout>`` serves it, with these substitutions and nothing else:

- the checkouts are clones of the local origin in ``tests/github_pull_fixture.py``, each
  with its ``origin`` set to a GitHub address, as a reader's clone has it;
- a fake ``gh`` first on ``PATH`` replays scrubbed real responses, and logs every call,
  which the transcript lists after each command;
- the clock is fixed, so ``fetched_at``, the window, and a state are the same every run;
- ``metabrowser.cache.acquire.remote_url_for`` clones ``https://github.com/octo/demo``
  from the local origin, for the one command that opens the repository as a mirror.

It shows what a checkout adds to the routes: the repository each spelling of a remote
names, a read that creates nothing, the first write publishing the ``unattached`` source,
records with no comparison, and a mirror acquired later attaching its store to the same
source and refreshing those records for their Files changed. Reading what this leaves,
with no ``gh`` at all, is ``tests/golden/cli-github-checkout.tryscript.md``.
"""

from __future__ import annotations

import json
import os
import subprocess
from itertools import count
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from metabrowser.builtin_plugins.github import pull_files_refresh, pull_list, pulls
from metabrowser.builtin_plugins.github.pull_catalog import read_catalog
from metabrowser.cache.urls import GitSource
from tests.checkout_replica import fingerprint
from tests.github_pull_fixture import (
    CANONICAL,
    FETCHED_AT,
    Origin,
    clone_checkout,
    files_scenario,
    git_env,
    in_a_stable_order,
    install_fake_gh,
    logged_gh_calls,
)
from tests.golden_harness import (
    Invocation,
    Labels,
    check_golden,
    check_recording,
    isolate_cli,
    label_home,
    origin_identity,
    quoted,
    run_metab,
)
from tests.required_tools import needs_git

pytestmark = [
    needs_git,
    pytest.mark.skipif(os.name != "posix", reason="owner-only cache is POSIX-only"),
]

PULLS = "/api/plugin/github/pulls"
PULL = "/api/plugin/github/pull"


class _Session:
    """The checkouts, the fake gh, the clock, and a transcript of each command."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: Origin) -> None:
        self.tmp_path = tmp_path
        self.monkeypatch = monkeypatch
        self.home = isolate_cli(tmp_path, monkeypatch).home
        self.origin = origin
        local = origin.url

        def remote_url_for(source: GitSource) -> str:
            return local if source.normalized == CANONICAL else source.normalized

        monkeypatch.setattr("metabrowser.cache.acquire.remote_url_for", remote_url_for)
        monkeypatch.setattr(pull_list, "utc_now", lambda: FETCHED_AT)
        monkeypatch.setattr(pulls, "utc_now", lambda: FETCHED_AT)
        generations = count(1)
        monkeypatch.setattr(pull_files_refresh, "uuid4", lambda: UUID(int=next(generations)))
        self.blocks: list[str] = []
        self.answers = files_scenario(origin)
        for name, value in install_fake_gh(tmp_path, self.answers).items():
            monkeypatch.setenv(name, value)

    def checkout(self, name: str, remote: str, *more: tuple[str, str]) -> Path:
        path = clone_checkout(self.origin, self.tmp_path / name, remote=remote)
        for remote_name, url in more:
            subprocess.run(
                ["git", "-C", str(path), "remote", "add", remote_name, url],
                check=True,
                capture_output=True,
                env=git_env(self.tmp_path),
            )
        return path

    def say(self, text: str) -> None:
        self.blocks.append(f"## {text}\n")

    def run(self, *args: str, **sections: list[str]) -> Invocation:
        result = run_metab(args)
        shown = [arg.removeprefix(f"{self.tmp_path}/") for arg in args]
        self.blocks.append(
            result.block(
                " ".join(quoted(arg) for arg in shown),
                **sections,
                gh=in_a_stable_order(logged_gh_calls(self.tmp_path)),
            )
        )
        return result

    def get(self, root: Path | str, route: str) -> Invocation:
        return self.run(str(root), "--api", route)

    def post(self, root: Path | str, route: str, body: dict[str, Any]) -> Invocation:
        path = self.tmp_path / "request.json"
        text = json.dumps(body)
        path.write_text(text + "\n", encoding="utf-8")
        return self.run(str(root), "--api", route, "--data", str(path), body=[text])


def _after(result: Invocation) -> dict[str, Any]:
    """The envelope a one-shot refresh printed after the job ended."""

    marker = "status: 200\n{"
    return json.loads(result.stdout[result.stdout.rindex(marker) + len("status: 200\n") :])


def _publication(result: Invocation) -> str:
    """What `/api/cache/source/<slug>` says of the source's publication."""

    return result.payload()["source"]["publication"]


def _answered(result: Invocation) -> dict[str, Any]:
    """The first answer a command printed: the refresh route's own."""

    start = result.stdout.index("{")
    return json.JSONDecoder().raw_decode(result.stdout[start:])[0]


def test_golden_a_checkouts_pull_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    session = _Session(tmp_path, monkeypatch, pull_origin)
    checkout = session.checkout("checkout", CANONICAL + ".git")
    fingerprints = {"checkout": fingerprint(checkout)}
    slug = origin_identity(CANONICAL).slug

    session.say("A read creates nothing: no home, no source, and no gh")
    for route in (
        f"{PULLS}?limit=0",
        f"{PULL}?number=10",
        "/api/plugin/github/pull-files?number=7",
    ):
        read = session.get(checkout, route)
        assert read.exit_code == 0, read.stderr
        assert (read.payload()["state"], read.payload()["reason"]) == ("absent", "not_cached")
    assert not session.home.exists()

    session.say("The list's first refresh publishes the source, with no store")
    listed = session.post(checkout, f"{PULLS}-refresh", {})
    assert listed.exit_code == 0, listed.stderr
    assert (_after(listed)["state"], _after(listed)["fetched"]) == ("current", 100)
    assert (_after(listed)["total"], _after(listed)["catalog_fetched"]) == (100, 102)
    source = session.home / "sources" / slug
    assert (source / "source.yml").is_file() and not (source / "store-alias.yml").exists()
    assert not list((session.home / "repository-stores").iterdir())
    cached = session.get(checkout, f"/api/cache/source/{slug}")
    assert _publication(cached) == "unattached"

    session.say("A record is read with gh alone, and has no comparison")
    record = session.post(checkout, f"{PULL}-refresh", {"number": 10, "retry": True})
    assert record.exit_code == 0, record.stderr
    after = _after(record)
    assert after["state"] == "current" and after["comparison_route"] is None
    assert after["record"]["comparison"] is None
    assert after["record"]["unavailable"] == {"comparison": "no_store"}
    shown = session.run(str(checkout), "--show", "/pull/10")
    assert shown.exit_code == 0, shown.stderr
    assert session.run(str(checkout), "--show", "/pulls").exit_code == 0
    body = session.get(checkout, f"{PULL}-markdown?number=10&part=body")
    assert body.exit_code == 0 and "html" in body.payload()
    files = session.post(checkout, "/api/plugin/github/pull-files-refresh", {"number": 7})
    assert files.exit_code == 0, files.stderr
    assert _after(files)["fetched"] == 2

    session.say("A subdirectory of the checkout, and an SSH remote, name the same repository")
    for root in (
        checkout / "src",
        session.checkout("ssh-checkout", "git@github.com:Octo/Demo.git"),
    ):
        fingerprints[root.name] = fingerprint(root if root.name != "src" else checkout)
        same = session.get(root, f"{PULLS}?limit=0")
        assert (same.payload()["source"], same.payload()["state"]) == (CANONICAL, "current")

    session.say("On a fork, origin is the fork, and that is the repository listed")
    fork = session.checkout(
        "fork-checkout",
        "https://github.com/someone/demo.git",
        ("upstream", CANONICAL + ".git"),
    )
    fingerprints["fork-checkout"] = fingerprint(fork)
    forked = session.get(fork, f"{PULLS}?limit=0")
    assert forked.payload()["source"] == "https://github.com/someone/demo"
    refused = session.post(fork, f"{PULLS}-refresh", {"retry": True})
    assert _after(refused)["last_refresh"]["outcome"] == "not_found_or_private"

    session.say("A remote the plugin's grammar refuses, and one that is not GitHub, list nothing")
    for name, remote in (
        ("odd-checkout", "https://github.com/under_score/demo.git"),
        ("elsewhere", "https://gitlab.example/octo/demo.git"),
    ):
        root = session.checkout(name, remote)
        fingerprints[name] = fingerprint(root)
        nothing = session.get(root, f"{PULLS}?limit=0")
        assert nothing.payload()["reason"] == "not_github"
        assert session.post(root, f"{PULLS}-refresh", {"retry": True}).exit_code == 1

    session.say(
        "A mirror opened later attaches its store to the same source, and a record written "
        "with no store is stale there whatever its age"
    )
    mirrored = session.get(CANONICAL, f"{PULL}?number=10")
    assert mirrored.exit_code == 0, mirrored.stderr
    assert mirrored.payload()["state"] == "stale"
    assert _publication(session.get(checkout, f"/api/cache/source/{slug}")) == "published"
    refreshed = session.post(CANONICAL, f"{PULL}-refresh", {"number": 10})
    assert _answered(refreshed)["refresh"] == "started"
    assert _after(refreshed)["record"]["comparison"] is not None
    assert _after(refreshed)["state"] == "current"

    session.say("The checkout's server offers no Files changed for that record: it has no store")
    again = session.get(checkout, f"{PULL}?number=10")
    assert again.payload()["comparison_route"] is None
    assert again.payload()["record"]["unavailable"] == {"comparison": "no_store"}

    session.say(
        "An explicit comparison Fetch attaches the cached store without changing the folder"
    )
    fetched = session.post(
        checkout, f"{PULL}-refresh", {"number": 10, "retry": True, "comparison": True}
    )
    assert fetched.exit_code == 0, fetched.stderr
    after = _after(fetched)
    assert after["pin"] is None and after["record"]["comparison"] is not None
    route = after["comparison_route"]
    assert route.startswith("/api/plugin/github/pull-comparison?")
    compared = session.get(checkout, route)
    assert compared.exit_code == 0, compared.stderr
    assert compared.payload()["manifest"]["files"]

    for name, before in fingerprints.items():
        root = checkout if name == "src" else tmp_path / name
        assert fingerprint(root) == before, name
    from urllib.parse import parse_qs, urlsplit

    labels = Labels()
    catalog = read_catalog(session.home, slug)
    assert catalog is not None
    labels.add(catalog.epoch, "<CATALOG_EPOCH>")
    query = parse_qs(urlsplit(route).query)
    labels.add(query["build"][0], "<BUILD>")
    labels.add(query["store"][0], "<STORE_TAG>")
    recorded = {
        "before": {"status": 200, "etag": None, "body": again.payload()},
        "started": {"status": 202, "etag": None, "body": _answered(fetched)},
        "ready": {"status": 200, "etag": None, "body": after},
    }
    check_recording(
        "github-checkout-comparison-responses.json",
        json.loads(labels.apply(json.dumps(recorded))),
        transcript="cli-ui-github-checkout-comparison.tryscript.md",
    )
    rendered = label_home(labels.apply("".join(session.blocks)), session.home)
    assert str(tmp_path) not in rendered and str(session.home) not in rendered
    assert "file://" not in rendered
    check_golden("cli-github-checkout.txt", rendered)
