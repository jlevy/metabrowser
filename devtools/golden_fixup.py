"""Re-apply elision patterns after `tryscript run --update` regenerates goldens.

`tryscript run --update` rewrites changed test blocks with literal captured
output, which clobbers the elision patterns the goldens rely on. This script
restores them so `make golden-update` is a single reviewable step:

* `[ROOT_ARG]` for the literal `[ROOT]` metavar in Typer's usage line, which
  tryscript would otherwise substitute with the test-file directory
* `[CWD]` for the sandbox directory in walk envelopes
* `[BUILTIN]` for the absolute checkout prefix of builtin plugin paths
* `[VERSION]` for the installed package version

It also strips trailing whitespace, which `tryscript run --update` preserves
from Rich's padded terminal output but `git diff --check` rejects; tryscript
trims line ends on both sides of a comparison, so stripping is match-safe.
"""

from __future__ import annotations

import re
from pathlib import Path

GOLDEN_DIR = Path(__file__).parent.parent / "tests" / "golden"

FIXUPS: list[tuple[str, str]] = [
    (r"Usage: metab \[OPTIONS\] \[ROOT\]", "Usage: metab [OPTIONS] [ROOT_ARG]"),
    (r"\S*/tryscript-[A-Za-z0-9]+", "[CWD]"),
    (r"\S+/builtin_plugins", "[BUILTIN]"),
    (r"^metab \d+\S*$", "metab [VERSION]"),
]


def main() -> None:
    for path in sorted(GOLDEN_DIR.glob("*.tryscript.md")):
        text = path.read_text()
        # The frontmatter defines the elision patterns themselves; only the
        # body after the closing "---" holds captured output to patch.
        frontmatter, separator, body = text.partition("\n---\n")
        fixed = body
        for pattern, replacement in FIXUPS:
            fixed = re.sub(pattern, replacement, fixed, flags=re.MULTILINE)
        fixed = re.sub(r"[ \t]+$", "", fixed, flags=re.MULTILINE)
        if fixed != body:
            path.write_text(frontmatter + separator + fixed)
            print(f"patterns restored: {path.name}")


if __name__ == "__main__":
    main()
