"""The link card on a real served page, in a real Chrome.

What a card says, when a rest asks for it, and which rests show none run browserlessly on
the exact module and app.js's own tooltip (``tests/dom/link-previews-session.js``, the
``shell.link-previews`` parity row). What only a browser can tell is held here, through
Chrome's own pointer and keys on a document the server renders: that the card comes up on
the tooltip's appear delay whatever the rest reads meanwhile, placed on its link and
holding still while the pointer moves within it, that it says what the link opens from the
data the page reads, a pull request's title once its catalog holds it though a rest came
first, and an outside link's where it goes, and that focus and a pointer that leaves show
none (docs/design-system.md, "Tooltips on Links").

So this serves a checkout of the GitHub stand-in, whose ``origin`` names
``github.com/octo/demo``, with a fake ``gh`` whose catalog holds pull request 8, and a
document linking a file with its author's title, a folder, pull request 8 twice (once by
its title), the checkout's head commit, the list of pull requests, and a page on another
site, then, past a screenful of words, the file again, whose card has no room below it,
beside the README, which the pointer reaches last, straight from the file's link while the
file's card is up, and whose own card must then show (the shell's bug H1, fixed).
``tests/dom/link-card-chrome.mjs`` rests Chrome's pointer on each link.

Without Chrome this skips (``require_chrome`` in ``tests/required_tools.py``). The test owns
everything it starts: the server stops when its stdin closes, and the measuring Node
process leads a process group of its own, which Chrome joins, so a run stopped at its
bound stops all of it (tests/process_group.py).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.github_pull_fixture import (
    CANONICAL,
    Origin,
    clone_checkout,
    git_env,
    install_fake_gh,
    pull_bodies,
)
from tests.process_group import GROUP_STOP_S, PROFILE_TEARDOWN_S, run_in_own_group
from tests.required_tools import require_chrome, require_git, require_node
from tests.test_github_pulls_stacks_chrome import stacks_scenario
from tests.test_nav_metadata_chrome import (
    _BANNER_BUDGET_S,
    _SERVER_STOP_S,
    _SERVING_BUDGET_S,
    _log_tail,
    _private,
    _read_port,
    _stop_server,
    _wait_until_serving,
)
from tests.test_nav_reveal_chrome import _serve

SESSION = Path(__file__).resolve().parent / "dom" / "link-card-chrome.mjs"
# A Chrome start, which tests/dom/chrome-session.mjs bounds at 30 s and the run's warm-up
# makes warm, then the page's load and its rests, each wait bounded in the script; under
# the suite's inner bound (tests/test_suite_gates.py, MAX_INNER_BOUND_S). On 2026-11-26
# in a Linux container the session took 21 s, nearly all of it the rests' own delays.
_MEASUREMENT_BUDGET_S = 48.0
LIFECYCLE_S = (
    _BANNER_BUDGET_S
    + _SERVING_BUDGET_S
    + _MEASUREMENT_BUDGET_S
    + GROUP_STOP_S
    + 2 * _SERVER_STOP_S
    + PROFILE_TEARDOWN_S
)
pytestmark = pytest.mark.timeout(LIFECYCLE_S + 10)

PULL = 8
DOCUMENT = "docs/cards.md"
AUTHOR_TITLE = "The project's guide"
# Paragraphs of words between the list and the last links: more than the 600 px a
# 1280 x 800 headless window gives the page, so they can sit at the pane's foot.
FILLER_PARAGRAPHS = 30


def add_card_document(checkout: Path, pull: dict[str, Any]) -> dict[str, object]:
    """Write the document the pointer rests on; what the session expects its cards to say.

    *pull* is the API's pull request 8, which the document links a second time by its
    title, which that link's card leaves out.
    """

    head, subject = subprocess.run(
        ["git", "-C", str(checkout), "log", "-1", "--format=%H%n%s"],
        check=True,
        capture_output=True,
        text=True,
        env=git_env(checkout.parent),
    ).stdout.splitlines()
    title = pull["title"]
    filler = "".join(f"Plain words, paragraph {index}.\n\n" for index in range(FILLER_PARAGRAPHS))
    (checkout / DOCUMENT).write_text(
        "# Cards\n\n"
        "Plain words, where the pointer waits between links.\n\n"
        f'- [The guide](guide.md "{AUTHOR_TITLE}")\n'
        "- [The source folder](../src/)\n"
        f"- [Pull request {PULL}]({CANONICAL}/pull/{PULL})\n"
        f"- [{title}]({CANONICAL}/pull/{PULL})\n"
        f"- [The head commit]({CANONICAL}/commit/{head})\n"
        f"- [The pull requests]({CANONICAL}/pulls)\n"
        "- [Another site](https://example.com/elsewhere)\n\n"
        f"{filler}"
        "At the foot, [the guide again](guide.md) and [the readme](../README.md).\n",
        encoding="utf-8",
    )
    return {
        "pull": PULL,
        "pullTitle": title,
        # As the catalog names it (pull_catalog.py, `catalog_search`).
        "pullState": "merged" if pull["merged"] else pull["state"],
        "commit": head,
        "commitSubject": subject,
        "authorTitle": AUTHOR_TITLE,
    }


def test_a_link_card_on_a_served_document_in_chrome(
    tmp_path: Path, pull_origin: Origin, chrome_profile: Path
) -> None:
    chrome = require_chrome()
    node = require_node()
    checkout = clone_checkout(pull_origin, tmp_path / "checkout")
    expected = add_card_document(checkout, pull_bodies(pull_origin)[PULL]["pull"])
    fake = install_fake_gh(tmp_path, stacks_scenario(pull_origin))
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(fake)
    tools = _private(tmp_path / "tools")
    (tools / "git").symlink_to(require_git())
    env["PATH"] = f"{tmp_path / 'fake-gh-bin'}{os.pathsep}{tools}"
    env["METABROWSER_CACHE_DIR"] = str(_private(tmp_path / "cache"))
    env["METABROWSER_CONFIG_DIR"] = str(_private(tmp_path / "config"))
    env["METABROWSER_LOG_LEVEL"] = "WARNING"
    log = tmp_path / "server.log"
    server = _serve(checkout, env, log)
    try:
        port = _read_port(server, log)
        _wait_until_serving(server, port, log)
        run = run_in_own_group(
            [
                node,
                str(SESSION),
                f"http://127.0.0.1:{port}/view/{DOCUMENT}",
                json.dumps(expected),
            ],
            timeout_s=_MEASUREMENT_BUDGET_S,
            env={**os.environ, "CHROME_BIN": chrome, "CHROME_PROFILES": str(chrome_profile)},
        )
    finally:
        _stop_server(server)
    if run.timed_out:
        pytest.fail(f"ran past {_MEASUREMENT_BUDGET_S:g} s; its steps:\n{run.stderr}")
    # Each rest's time and card, and the count of checks, shown with the output when it fails.
    print(run.stderr + run.stdout)
    assert run.returncode == 0, f"{run.stderr[-6000:]}\nserver: {_log_tail(log)}"
    passed = re.fullmatch(r"link card in Chrome: (\d+) checks passed\n", run.stdout)
    assert passed is not None and int(passed.group(1)) > 0, run.stdout
