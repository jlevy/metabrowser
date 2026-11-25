"""Every age draws in its freshness ink, by construction (docs/design-system.md, "Age").

An age is drawn by one builder, `MetabrowserFormatters.ageLabel` and `ageLabelHtml` in
`static/formatters.js`, which plugins reach as `metabrowser.ageLabel` and
`metabrowser.ageLabelHtml`, and told again by `metabrowser.retellAge` (`plugin-sdk-views.js`),
which swaps its freshness class by the class namespace. The builder puts the age's
freshness class on it, and that class's one rule in `static/styles.css` sets its ink,
weight, and numerals. Two things could still bypass it, and these guards hold the
mechanism rather than restating any colour:

1. **A stylesheet overriding the ink.** A rule whose subject is an age, by a freshness
   class or by a call site's own class (`.github-pulls-age`, `.git-graph-age`), that sets
   the ink, weight, size, or numerals outranks the shared rule wherever its selector is
   more specific: `.github-pulls-tail > .github-pulls-age { color: var(--muted) }` drew
   every Pulls row's age gray (mb-daxw). A call site's class places an age and nothing
   more, and every age's call-site class ends in `-age`, so this check can find it.
2. **A module painting the class itself.** A module that takes the primitive's class from
   `formatAge` or `MetabrowserFormatters.age` and puts it on an element draws an age the
   builder does not, and can drop the class. Their label is for words: a sentence or an
   accessible name.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "metabrowser"
SHARED_RULE_SHEET = SOURCE / "static" / "styles.css"

# What the freshness class owns: an age's ink, its weight, its numerals, and (by setting
# none) its size, which is its line's.
OWNED_PROPERTIES = ("color", "font-weight", "font-size", "font", "font-variant-numeric")
FRESHNESS_CLASS = re.compile(r"^age-(?:live|sec|min|hr|day|wk|old)$")
# A call site's own class for an age, or for the box an age sits alone in.
CALL_SITE_CLASS = re.compile(r"(?:^|-)age$")

# The primitive's own modules: the builder, and the SDK that forwards it.
PRIMITIVE_MODULES = {
    SOURCE / "static" / "formatters.js",
    SOURCE / "static" / "plugin-sdk.js",
    SOURCE / "static" / "plugin-sdk-views.js",
}


def _tracked(pattern: str) -> list[Path]:
    listed = subprocess.run(
        ["git", "ls-files", "--", pattern],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    return [ROOT / name for name in listed if "/vendor/" not in name]


def _rules(css: str) -> list[tuple[int, str, str]]:
    """Each innermost rule as (line, selector list, declarations), comments removed."""

    css = re.sub(r"/\*.*?\*/", lambda match: re.sub(r"[^\n]", " ", match.group()), css, flags=re.S)
    return [
        (css.count("\n", 0, match.start(1)) + 1, match.group(1).strip(), match.group(2))
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css)
    ]


def _split_top_level(text: str, separator: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    for index, character in enumerate(text):
        if character in "([":
            depth += 1
        elif character in ")]":
            depth -= 1
        elif character == separator and depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return [part.strip() for part in parts if part.strip()]


def _subject_classes(selector: str) -> set[str]:
    """The classes a complex selector's subject must have, or may have through `:is()`."""

    compounds = re.split(r"\s*[>+~]\s*|\s+(?![^(]*\))", selector.strip())
    subject = re.sub(r":not\((?:[^()]|\([^()]*\))*\)", "", compounds[-1])
    return set(re.findall(r"\.([\w-]+)", subject))


def _sets_owned_property(declarations: str) -> list[str]:
    names = re.findall(r"(?:^|;)\s*([\w-]+)\s*:", declarations)
    return [name for name in names if name in OWNED_PROPERTIES]


def test_no_stylesheet_inks_an_age_but_the_freshness_rule() -> None:
    findings: list[str] = []
    for sheet in _tracked("*.css"):
        for line, selectors, declarations in _rules(sheet.read_text(encoding="utf-8")):
            if selectors.startswith("@"):
                continue
            owned = _sets_owned_property(declarations)
            if not owned:
                continue
            for selector in _split_top_level(selectors, ","):
                classes = _subject_classes(selector)
                freshness = {name for name in classes if FRESHNESS_CLASS.match(name)}
                if sheet == SHARED_RULE_SHEET and freshness and freshness == classes:
                    # The shared rule itself, `:is(.age-live, …, .age-old)`. It sets no size
                    # either: an age reads at the size of the text it sits in ("Type Scale").
                    sized = [name for name in owned if name in ("font-size", "font")]
                    if sized:
                        findings.append(f"{sheet.relative_to(ROOT)}:{line}: {selector} sizes ages")
                    continue
                ages = freshness | {name for name in classes if CALL_SITE_CLASS.search(name)}
                if ages:
                    where = sheet.relative_to(ROOT)
                    findings.append(f"{where}:{line}: {selector} sets {', '.join(owned)}")
    assert findings == [], (
        "only the freshness class's rule may set an age's ink, weight, size, or numerals; "
        "place an age with its call site's class and nothing more:\n" + "\n".join(findings)
    )


# The primitive's class read off its answer: destructured, read at once, or read off a name
# the answer was kept in.
_PRIMITIVE_CALL = r"(?:\bformatAge|\bMetabrowserFormatters\??\.age)\("
_DESTRUCTURED = re.compile(r"\{[^{}]*\bclassName\b[^{}]*\}\s*=\s*[^;]*?" + _PRIMITIVE_CALL)
_READ_AT_ONCE = re.compile(_PRIMITIVE_CALL + r"(?:[^()]|\([^()]*\))*\)\??\.className\b")
_KEPT = re.compile(r"\b(?:const|let|var)\s+(\w+)\s*=\s*[^;]*?" + _PRIMITIVE_CALL)


def test_no_module_paints_an_age_from_the_primitives_class() -> None:
    findings: list[str] = []
    for module in _tracked("src/metabrowser/*.js"):
        if module in PRIMITIVE_MODULES:
            continue
        text = module.read_text(encoding="utf-8")
        where = module.relative_to(ROOT)
        for pattern in (_DESTRUCTURED, _READ_AT_ONCE):
            for match in pattern.finditer(text):
                findings.append(f"{where}:{text.count(chr(10), 0, match.start()) + 1}")
        for match in _KEPT.finditer(text):
            if re.search(rf"\b{match.group(1)}\??\.className\b", text[match.end() :]):
                findings.append(f"{where}:{text.count(chr(10), 0, match.start()) + 1}")
    assert findings == [], (
        "draw an age with ageLabel or ageLabelHtml, which put its freshness class on it, "
        "not with formatAge's class:\n" + "\n".join(findings)
    )


# A class in the freshness namespace, as a stylesheet selects it or a module names it.
_NAMESPACED_CSS = re.compile(r"\.(age-[\w-]+)")
_NAMESPACED_JS = re.compile(r"[\"'`](age-[\w-]*)")


def test_the_age_namespace_holds_only_freshness_classes() -> None:
    # `retellAge` (plugin-sdk-views.js) swaps an age's freshness class by its namespace,
    # age-*, and keeps every other class. That is right only while every class in the
    # namespace is a freshness class and no call site's own class is in it.
    findings: list[str] = []
    for path, pattern in [
        *((sheet, _NAMESPACED_CSS) for sheet in _tracked("*.css")),
        *((module, _NAMESPACED_JS) for module in _tracked("src/metabrowser/*.js")),
    ]:
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            if not FRESHNESS_CLASS.match(match.group(1)):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{path.relative_to(ROOT)}:{line}: {match.group(1)}")
    assert findings == [], (
        "a class beginning `age-` is a freshness class, which retellAge replaces; name a call "
        "site's class `<surface>-age`:\n" + "\n".join(findings)
    )
