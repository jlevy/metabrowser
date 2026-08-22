"""Hold the rule that Metabrowser shows one tooltip, and it is its own.

The app has an anchored, styled, themed tooltip. A native ``title`` is a second
tooltip system running beside it: it cannot be styled or placed, it appears on
the platform's timer rather than ours, and on a surface that already announces
a tooltip the reader gets two of them side by side on different timers. That
happened, on the navigation heading, which is why this check exists rather than
a sentence in a document that nothing enforces.

**The rule.** No ``title`` attribute, and no ``.title =`` assignment, in markup
the app owns — the browser sources, the built-in plugins, and the HTML the
server renders. Use ``data-tip-text`` for a short string, which app.js turns
into the app's tooltip from a delegated listener, or ``mb.tooltip.show`` for
rich content.

**What this is not.** It is not a rule about accessible names. ``aria-label``
is untouched and still required wherever it was: a screen reader does not read
``data-tip-text``, so a glyph-only control needs both. ``<title>`` inside an
SVG is a different element with a different job and is left alone.

Run it through ``make lint``. It prints file and line, because the fix is
always the same one-word edit and the only question is where.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SEARCH_ROOTS = (
    ROOT / "src" / "metabrowser" / "static",
    ROOT / "src" / "metabrowser" / "builtin_plugins",
    ROOT / "src" / "metabrowser",
)
SUFFIXES = (".js", ".py", ".html", ".css")

# `title=` as an HTML attribute, and `.title =` as a DOM assignment. Both are
# the visible-tooltip mechanism this rule replaces.
_ATTRIBUTE = re.compile(r"""(?<![\w-])title\s*=\s*["'{]""")
_ASSIGNMENT = re.compile(r"""\.title\s*=\s*(?!=)""")

# Places the attribute is not the browser's tooltip and the rule does not
# reach. Each is a path suffix and the reason it is here.
ALLOWED: dict[str, str] = {
    "static/vendor": "vendored third-party assets, not ours to edit",
    "static/types.d.ts": "type declarations describe the DOM, they do not render",
}

# A document's <title> is the tab's name, not a tooltip.
_DOCUMENT_TITLE = re.compile(r"<title>|</title>|<title\s")


@dataclass(frozen=True, slots=True)
class Finding:
    path: Path
    line: int
    text: str


def _allowed(path: Path) -> str | None:
    text = path.as_posix()
    for fragment, reason in ALLOWED.items():
        if fragment in text:
            return reason
    return None


def _scan(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if _DOCUMENT_TITLE.search(line):
            continue
        if _ATTRIBUTE.search(line) or _ASSIGNMENT.search(line):
            findings.append(Finding(path, number, line.strip()))
    return findings


def _candidates() -> list[Path]:
    seen: set[Path] = set()
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.suffix in SUFFIXES and path.is_file() and _allowed(path) is None:
                seen.add(path)
    return sorted(seen)


def main() -> int:
    findings: list[Finding] = []
    for path in _candidates():
        findings.extend(_scan(path))

    if findings:
        print("tooltips: the app shows its own, so `title` is not the mechanism", file=sys.stderr)
        for finding in findings:
            relative = finding.path.relative_to(ROOT)
            print(f"  {relative}:{finding.line}: {finding.text[:96]}", file=sys.stderr)
        print(
            '\nUse data-tip-text="..." for a short string, or mb.tooltip.show for rich\n'
            "content. Keep aria-label where it is: it is the accessible name, not a\n"
            "tooltip, and this attribute is not read by a screen reader.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
