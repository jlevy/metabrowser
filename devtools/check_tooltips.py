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

**And one tooltip size.** The app's tooltip reads at ``--tooltip-font-size``,
which is body size, and its subordinate lines at ``--tooltip-detail-font-size``.
Neither may be spelled as some other token or as a literal: pointing a tooltip
at ``--ui-small-font-size`` is what made its size a side effect of a decision
about chips and counts. KPress's own tooltip inside an embedded document is not
ours and is left alone.

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


# The rules that own a tooltip's type size, and the only values they may take.
TOOLTIP_SIZE_RULES: dict[str, str] = {
    ".custom-tooltip": "var(--tooltip-font-size)",
    ".tip-detail": "var(--tooltip-detail-font-size)",
}

_STYLESHEET = ROOT / "src" / "metabrowser" / "static" / "styles.css"


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


def _size_findings() -> list[Finding]:
    """Each tooltip rule sets its size from the tooltip's own token."""

    findings: list[Finding] = []
    css = _STYLESHEET.read_text(encoding="utf-8")
    for selector, expected in TOOLTIP_SIZE_RULES.items():
        marker = f"{selector} {{"
        if marker not in css:
            findings.append(
                Finding(_STYLESHEET, 0, f"{selector} is gone; update TOOLTIP_SIZE_RULES")
            )
            continue
        start = css.index(marker)
        block = css[start : css.index("}", start)]
        match = re.search(r"font-size:\s*([^;]+);", block)
        if match is None:
            findings.append(
                Finding(_STYLESHEET, css.count("\n", 0, start) + 1, f"{selector} sets no font-size")
            )
        elif match.group(1).strip() != expected:
            findings.append(
                Finding(
                    _STYLESHEET,
                    css.count("\n", 0, start + match.start()) + 1,
                    f"{selector} sets font-size: {match.group(1).strip()}, not {expected}",
                )
            )
    return findings


def main() -> int:
    findings: list[Finding] = []
    for path in _candidates():
        findings.extend(_scan(path))
    size_findings = _size_findings()

    if size_findings:
        print("tooltips: the size comes from the tooltip's own token", file=sys.stderr)
        for finding in size_findings:
            print(
                f"  {finding.path.relative_to(ROOT)}:{finding.line}: {finding.text}",
                file=sys.stderr,
            )
        print(
            "\nA tooltip reads at body size. Pointing it at a chrome token makes its\n"
            "size a side effect of a decision about chips and counts.",
            file=sys.stderr,
        )

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
    return 1 if size_findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
