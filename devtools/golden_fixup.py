"""Re-apply elision patterns after `tryscript run --update` regenerates goldens.

`tryscript run --update` rewrites changed test blocks with literal captured
output, which clobbers the elision patterns the goldens rely on. This script
restores them so `make golden-update` is a single reviewable step:

* `[ROOT_ARG]` for the literal `[ROOT]` metavar in Typer's usage line, which
  tryscript would otherwise substitute with the test-file directory
* `[CWD]` for the sandbox directory in walk envelopes
* `[BUILTIN]` for the absolute checkout prefix of builtin plugin paths
* `[VERSION]` for the installed package version
* the KPress rendered document body, which is tens of kilobytes of icon sprite
  and would make the transcript unreviewable; the POST case keeps its overridden
  heading visible so the transcript still proves the source override took effect
* the pending-tally diagnostic's stderr line, which carries a wall clock
* the host facts in watcher `reason` values -- the filesystem the served root
  sits on and the backend that made available -- which differ between the
  author's Mac and CI, and the engine sequence in the pending-tally
  diagnostic, which counts internal change batches

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
    # Not \S*: the sandbox path is often quoted in a JSON envelope, and a
    # non-space run swallows the opening quote along with the path.
    (r'[^\s"]*/tryscript-[A-Za-z0-9]+', "[CWD]"),
    (r"/\S*/builtin_plugins", "[BUILTIN]"),
    # The trailing group is the build annotation a checkout adds; see
    # metabrowser.build_version. It varies per commit, so it elides with the
    # version rather than beside it.
    (r"^metab \d+\S*( \([^)]*\))?$", "metab [VERSION]"),
    # The rendered document body. The POST case is matched first so its
    # overridden heading survives: it is the only thing in that transcript that
    # proves `source_text` reached the renderer.
    (
        r'^  "html": ".*?(<h1 id=\\"overridden\\">Overridden</h1>).*",$',
        r'  "html": "[..]\1[..]",',
    ),
    (r'^  "html": ".{300,}",$', '  "html": "[..]",'),
    (r"^.*pending folder tallies diagnostic.*$", "[..]"),
    # Host facts, not behavior: the filesystem type the served root sits on
    # (apfs here, ext4 on CI) and the watch backend it made available. These
    # were elided by hand once and silently re-pinned by the next
    # `golden-update`, which is the failure this rule exists to stop.
    # Everything around them stays pinned, `mode` included, which is the part
    # a regression would change.
    (r'"reason": "fs=[^"]*"', '"reason": "[..]"'),
    (r'"watch_reason": "fs=[^"]*"', '"watch_reason": "[..]"'),
    (r'"reason": "inventory-[^"]*"', '"reason": "[..]"'),
    # The provider's change-batch counter at the moment the diagnostic ran. It
    # is worth reporting and not worth pinning: no reader depends on the count,
    # and a provider that batches differently would fail the transcript for a
    # difference that is not a defect. Anchored to the line above so the schema
    # versions elsewhere in these goldens keep their exact values.
    (
        r'(^    "contract": "inventory-provider-v1",\n    "version": )\d+',
        r"\1[..]",
    ),
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
