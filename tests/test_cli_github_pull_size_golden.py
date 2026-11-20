"""Golden transcript: the size a pull request pushes, through ``metab --api``.

``GET github/pull-size`` answers the size of the comparison a pull request's record names,
its head against the merge base, as Git pushes it and as a patch
(:mod:`metabrowser.builtin_plugins.github.pull_size`). This drives it in-process, as
``tests/test_cli_github_pull_image_golden.py`` drives the image route, and writes
``tests/golden/cli-github-pull-size.txt``: the pair the envelope's ``size_route`` names is
measured, its size is kept beside the store so a fresh process answers without measuring,
and each refusal has its own code.

The pushed size is zlib's output, which can differ by a few bytes between zlib builds, so
the transcript names it ``<PUSHED>`` and the test checks it against the pack Git writes;
the patch's size, commits, and merge base are Git's text and are pinned as they are.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from metabrowser.git.change_size import BANK_DIRECTORY, PACK_ARGS
from tests.git_pin_harness import git_env
from tests.github_pull_fixture import CANONICAL, Origin
from tests.golden_harness import (
    Labels,
    check_golden,
    label_home,
    mask_pushed_bytes,
    normalize_pull_comparison_scopes,
    run_metab,
)
from tests.test_cli_github_pull_golden import PULL, ROUTE, _Session


def test_golden_a_pull_requests_size_is_measured_once_and_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pull_origin: Origin
) -> None:
    session = _Session(tmp_path, monkeypatch, pull_origin)
    selected = f"{PULL}/7"
    acquired = session.run(selected, "--no-serve")
    assert acquired.exit_code == 0, acquired.stderr
    envelope = run_metab((selected, "--api", f"{ROUTE}?number=7")).payload()
    route = envelope["size_route"]
    assert route.startswith("/api/plugin/github/pull-size?number=7&")
    comparison = envelope["record"]["comparison"]

    answer = session.run(selected, "--api", route)
    assert answer.exit_code == 0, answer.stderr
    size = answer.payload()["size"]
    assert size["state"] == "measured" and size["head"] == comparison["head"]
    assert size["commits"] >= 1 and size["diff_bytes"] > 0

    # The pushed size is the pack Git writes for the head against the merge base.
    stores = sorted((session.home / "repository-stores").glob("*/repository.git"))
    assert len(stores) == 1, stores
    pack = subprocess.run(
        ["git", "--git-dir", str(stores[0]), *PACK_ARGS],
        input=f"{size['head']}\n^{size['base']}\n".encode(),
        env=git_env(tmp_path),
        check=True,
        capture_output=True,
    ).stdout
    assert size["pushed_bytes"] == len(pack)

    # Kept beside the store: the next process answers it from the bank.
    banks = sorted(stores[0].parent.glob(f"{BANK_DIRECTORY}/*.json"))
    assert len(banks) == 1, banks
    assert json.loads(banks[0].read_text())["sizes"]
    again = session.run(selected, "--api", route)
    assert again.payload() == answer.payload()

    # Each refusal says what it is.
    other = route.replace(f"left={comparison['base']}", "left=" + "0" * 40)
    session.blocks.append("")
    expired = session.run(selected, "--api", other)
    assert expired.exit_code != 0 and expired.payload()["code"] == "snapshot_expired"
    malformed = session.run(selected, "--api", route.replace("right=", "right=x"))
    assert malformed.exit_code != 0 and malformed.payload()["code"] == "invalid_pull_size"

    labels = Labels()
    labels.origin(CANONICAL)
    text = normalize_pull_comparison_scopes(
        label_home(labels.apply("".join(session.blocks)), session.home)
    )
    # The malformed request names the store after an ID the normalizer cannot match.
    text = re.sub(r"(&store=)[0-9a-f]{16}", r"\1<STORE>", mask_pushed_bytes(text))
    assert str(tmp_path) not in text
    check_golden("cli-github-pull-size.txt", text)
