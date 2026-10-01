"""Run the modules that rewrite goldens, with no skip allowed.

``make golden-update`` claims to regenerate every recording and every in-process
transcript. A recorder that skips, because Node is missing, the installed Git is below
the acquisition floor, or the run is root, regenerates nothing and still reports
success, so the claim would then depend on the host without saying so.

This runs pytest on the named modules with ``GOLDEN_UPDATE=1``, which the golden harness
reads, and ``METABROWSER_STRICT_SKIPS=all``. The second is the suite's own switch for
judging skips (``tests/suite_gates.py``), at the level where none stands: a skipped test
fails with its reason, tier or not, opt-out or not. There is one place that says which
skips are allowed, and this adds no second one.

    python -m devtools.golden_update tests/test_one.py tests/test_two.py

Every argument is passed to pytest, so an option may be given beside the modules.
"""

from __future__ import annotations

import os
import sys

import pytest

from devtools.check_goldens import UPDATE_ENV

# ``tests/suite_gates.py`` owns these two; they are spelled here because ``devtools``
# must import without the test tree.
STRICT_SKIPS_ENV = "METABROWSER_STRICT_SKIPS"
STRICT_SKIPS_ALL = "all"


def main(arguments: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if arguments is None else arguments
    if not arguments:
        print("usage: python -m devtools.golden_update <test module>...", file=sys.stderr)
        return 2
    os.environ[UPDATE_ENV] = "1"
    os.environ[STRICT_SKIPS_ENV] = STRICT_SKIPS_ALL
    return int(pytest.main(["-rs", *arguments]))


if __name__ == "__main__":
    sys.exit(main())
