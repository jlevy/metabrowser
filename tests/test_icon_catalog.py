"""The icon catalog, ``docs/design-system-icons.md``, is every icon the product draws.

The catalog's tables list each icon once per place it is defined: its name, the source
it comes from, what it means, the file that defines it, its ink, and its size. These
checks hold the tables to the code in both directions, as ``tests/test_keymap.py`` holds
the keyboard table to the keys the app binds:

- the shell's registry (``static/icons.js``) and every other SVG glyph a browser source
  defines by name are the catalog's drawn rows, every registry glyph has a caller, and no
  browser source or the server's page draws an SVG it does not define by name;
- every glyph character a browser source types, written as itself or as an escape, is a
  text row with the files that type it, except in a comment or a console message;
- a stylesheet's masked glyph, an SF Symbol the macOS app draws, and the change letters
  the status tables give are rows, and each row's file says so;
- two rows naming one upstream glyph draw it the same, and a row's upstream id is the one
  its definition's comment names;
- a fold expander draws KPress's expand/contract pair, the drawings of KPress's own sprite,
  and never the registry's chevron;
- every rule that inks a masked glyph is drawn again in CanvasText in forced colors, which
  force the mask's background to Canvas;
- the type registry's shapes are cataloged and named for the categories and formats that
  take them, and its schema permits exactly those shapes;
- each token a row's ink or size names is declared by a shipped stylesheet;
- the source kinds, the three marks for a kind of root, are the identity route's kinds, each
  with a glyph in the server's glyph file that is a different drawing from the others' and
  from the ordinary folder's, no script holds a copy of one, and the macOS app's marks are
  the same glyphs and words.

Each failure names the icon, so the fix is to catalog it, or to draw what the catalog
already has instead.
"""

from __future__ import annotations

import base64
import html
import json
import re
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple, get_args
from urllib.parse import unquote

from metabrowser import kpress_adapter, shell_glyphs
from metabrowser.root_identity import KIND_LABELS, IdentityKind

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE = REPO_ROOT / "src" / "metabrowser"
STATIC = PACKAGE / "static"
BUILTIN_PLUGINS = PACKAGE / "builtin_plugins"
CATALOG = REPO_ROOT / "docs" / "design-system-icons.md"
REGISTRY = STATIC / "icons.js"
SOURCE_KIND_GLYPHS = STATIC / "source-kind-glyphs.json"
SHELL_GLYPHS = PACKAGE / "shell_glyphs.py"
TYPE_REGISTRY = PACKAGE / "data" / "file-rollup-format" / "recommended-file-types.toml"
TYPE_SCHEMA = PACKAGE / "data" / "file-rollup-format" / "file-type-registry.schema.json"
MACOS_SOURCES = REPO_ROOT / "apps" / "macos" / "Sources"

HEADER = ("Icon", "Source", "Meaning", "Defined in", "Ink", "Size")
# The sources a row may name, by what defines its drawing.
DRAWN = ("Registry", "Plugin", "View bundle")
SOURCES = frozenset(
    {*DRAWN, "CSS mask", "Shell", "Text", "Letter", "SF Symbol", "App glyph", "App mark"}
)

# What the registry's callers write: a property of the registry, by its global's name or the
# `ICONS` and `ICON_SVG` aliases the shell's scripts give it, or of the SDK's proxy of it,
# `mb.icons` in a plugin and `metabrowser.icons` or `sdk.icons` in the shell; or the name a
# plugin's helper looks one up by. Any other object named `icons` is not the registry.
_REGISTRY_USE = re.compile(
    r"(?:\b(?:ICONS|ICON_SVG|MetabrowserIcons)|\b(?:mb|metabrowser|sdk|sdk\(\))\??\.icons)"
    r"\??\.([A-Za-z]\w*)\b"
    r"|\b(?:shellIcon|registryIcon)\(\"(\w+)\"\)"
)
# Properties of the registry object that are not glyphs.
_NOT_GLYPHS = frozenset({"withClass"})
# A glyph defined by name: an identifier, then `:` or `=`, an optional line comment, and a
# string that opens an SVG.
_SVG_DEFINITION = re.compile(r"\b(\w+)\s*[:=]\s*(?://[^\n]*\n\s*)?[\"'`]<svg\b")
_UPSTREAM_COMMENT = re.compile(r"//\s*Lucide `([a-z0-9-]+)`")
# A glyph shell_glyphs.py defines: a comment ending in its Lucide id, then its `_SVG` constant.
_SHELL_GLYPH_DEFINITION = re.compile(
    r"^# [^\n]*Lucide `([a-z0-9-]+)`\.?\n(\w+_SVG): Final = ", re.M
)
# Characters that are marks rather than words: arrows, technical symbols, geometric shapes,
# miscellaneous symbols, dingbats, more arrows and math marks such as ⧉, the
# multiplication sign a close button might use, the guillemets a pager or a breadcrumb
# might use, the vertical and midline ellipses of a "more" menu, and pictographs.
_GLYPH = re.compile("[«»×‹›←-⇿⋮⋯⌀-⏿■-◿☀-➿⤀-⧿⬀-⯿\U0001f300-\U0001faff]")
# A character a script writes as an escape: JavaScript's `\u203A` and `\u{1F5C2}`, or an
# HTML character reference such as `&rsaquo;` or `&#8250;`.
_SCRIPT_ESCAPE = re.compile(
    r"\\u\{([0-9a-fA-F]{1,6})\}|\\u([0-9a-fA-F]{4})"
    r"|(&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z]\w*);)"
)
# A character a stylesheet writes as an escape, such as `content: "\203A"`.
_CSS_ESCAPE = re.compile(r"\\([0-9a-fA-F]{1,6})\s?")
# A call whose arguments are a message to a developer, not markup a reader sees.
_CONSOLE_CALL = re.compile(r"\bconsole\.\w+\(")
# A stylesheet's SVG drawn from a data URI, in either quote or none, as text or base64.
_SVG_DATA_URI = re.compile(r"""url\(\s*(["']?)data:image/svg\+xml([^,]*),(.*?)\1\s*\)""", re.DOTALL)
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"(?<![:\\\"'`])//.*$", re.MULTILINE)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_CODE_SPAN = re.compile(r"`([^`]+)`")
_TOKEN = re.compile(r"`(--[\w-]+)`")
_TOKEN_DECLARATION = re.compile(r"(--[\w-]+)\s*:")
# A symbol of KPress's icon sprite: its Lucide id and its drawing.
_KPRESS_SYMBOL = re.compile(r'<symbol id="kpress-icon-([a-z0-9-]+)"[^>]*>(.*?)</symbol>', re.DOTALL)
# A fold expander's two glyphs, closed and open, by the selector that draws each
# (docs/design-system.md, "Fold Expanders").
_FOLD_GLYPHS = {
    ".fold-expander::before": "chevrons-up-down",
    '.fold-expander[aria-expanded="true"]::before': "chevrons-down-up",
}
# A stylesheet's forced-colors block; a rule whose block holds no other block; the state a
# selector is in (a pseudo-class, with its arguments, or an attribute), for the element it
# names; and a declaration of a background's color, a mask's ink.
_FORCED_COLORS = re.compile(r"@media\s*\(\s*forced-colors\s*:\s*active\s*\)\s*\{")
_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
_SELECTOR_STATE = re.compile(r"(?<!:):[a-z-]+(?:\([^()]*\))?|\[[^\]]*\]")
_BACKGROUND_COLOR = re.compile(r"(?:^|;)\s*background(?:-color)?\s*:\s*([^;]+)")


class Row(NamedTuple):
    """One catalog row, with the kind its section names."""

    kind: str
    icon: str
    upstream: str | None
    source: str
    meaning: str
    defined_in: tuple[str, ...]
    ink: str
    size: str


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split(" | ")]


def _catalog(text: str | None = None) -> list[Row]:
    """The rows of every table in the catalog whose header is the catalog's."""
    lines = (CATALOG.read_text(encoding="utf-8") if text is None else text).splitlines()
    rows: list[Row] = []
    kind = ""
    in_table = False
    for line in lines:
        if line.startswith("## "):
            kind = line[3:].strip()
        if not line.startswith("|"):
            in_table = False
            continue
        cells = _cells(line)
        if tuple(cells) == HEADER:
            in_table = True
            continue
        if not in_table or set(line.replace("|", "").strip()) <= {"-", " "}:
            continue
        assert len(cells) == len(HEADER), f"a catalog row has {len(cells)} cells: {line}"
        icon_cell, source, meaning, defined_in, ink, size = cells
        spans = _CODE_SPAN.findall(icon_cell)
        assert spans, f"a catalog row names no icon: {line}"
        rows.append(
            Row(
                kind=kind,
                icon=spans[0],
                upstream=spans[1] if len(spans) > 1 else None,
                source=source,
                meaning=meaning,
                defined_in=tuple(_CODE_SPAN.findall(defined_in)),
                ink=ink,
                size=size,
            )
        )
    return rows


def _resolve(path: str) -> Path:
    """A catalog path: from the repository's root, or from the package's."""
    for base in (REPO_ROOT, PACKAGE):
        if (base / path).exists():
            return base / path
    raise AssertionError(f"the catalog names a file that does not exist: {path}")


def _relative(path: Path) -> str:
    """How the catalog names *path*: from the package for its sources, else the root."""
    return str(path.relative_to(PACKAGE if path.is_relative_to(PACKAGE) else REPO_ROOT))


def _browser_scripts() -> Iterator[Path]:
    yield from sorted(path for path in STATIC.glob("*.js"))
    yield from sorted(BUILTIN_PLUGINS.rglob("*.js"))
    yield from sorted(BUILTIN_PLUGINS.rglob("*.mjs"))


def _stylesheets() -> Iterator[Path]:
    yield from sorted(STATIC.glob("*.css"))
    yield from sorted(BUILTIN_PLUGINS.rglob("*.css"))


def _script_code(path: Path) -> str:
    return _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", path.read_text(encoding="utf-8")))


def _script_escapes_decoded(code: str) -> str:
    """*code* with each JavaScript escape and HTML character reference as its character."""

    def character(match: re.Match[str]) -> str:
        if match[3] is not None:
            return html.unescape(match[3])
        return chr(int(match[1] or match[2], 16))

    return _SCRIPT_ESCAPE.sub(character, code)


def _css_escapes_decoded(css: str) -> str:
    """*css* with each CSS escape as its character."""
    return _CSS_ESCAPE.sub(lambda match: chr(min(int(match[1], 16), 0x10FFFF)), css)


def _closing_paren(code: str, start: int) -> int | None:
    """Where the call whose arguments begin at *start* closes, skipping strings."""
    depth = 1
    at = start
    while at < len(code):
        char = code[at]
        if char in "\"'`":
            at += 1
            while at < len(code) and code[at] != char:
                at += 2 if code[at] == "\\" else 1
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return at
        at += 1
    return None


def _without_console_messages(code: str) -> str:
    """*code* without the arguments of its `console.*` calls, which no reader sees."""
    kept: list[str] = []
    end = 0
    for match in _CONSOLE_CALL.finditer(code):
        if match.start() < end:
            continue
        closing = _closing_paren(code, match.end())
        if closing is None:
            break
        kept.append(code[end : match.end()])
        end = closing
    kept.append(code[end:])
    return "".join(kept)


def _shell_template() -> str:
    """The page the server writes, `index`'s HTML, without its comments."""
    source = (PACKAGE / "server.py").read_text(encoding="utf-8")
    start = source.index("<!DOCTYPE html>")
    return _HTML_COMMENT.sub("", source[start : source.index("</html>", start)])


def _svg_definitions(text: str) -> dict[str, tuple[str, str | None]]:
    """Each glyph *text* defines by name: its drawing's inner markup and upstream id."""
    found: dict[str, tuple[str, str | None]] = {}
    lines = text.splitlines()
    for match in _SVG_DEFINITION.finditer(text):
        name = match[1]
        opened = text.index("<svg", match.start())
        inner = text[text.index(">", opened) + 1 : text.index("</svg>", opened)]
        # The id is commented on the definition's own line, or on a comment line above it.
        line = text.count("\n", 0, match.start())
        comment = _UPSTREAM_COMMENT.search(f"{lines[line]}\n{text[match.start() : opened]}")
        if comment is None and line > 0 and lines[line - 1].lstrip().startswith("//"):
            comment = _UPSTREAM_COMMENT.search(lines[line - 1])
        found[name] = (inner, comment[1] if comment else None)
    return found


def _drawing(inner: str) -> str:
    """A drawing's elements as one string to compare: one quote style, no whitespace runs."""
    return " ".join(inner.replace("'", '"').split())


def _mask_glyphs() -> dict[tuple[str, str], str]:
    """Each stylesheet glyph drawn from an SVG data URI: (file, first selector) to drawing."""
    found: dict[tuple[str, str], str] = {}
    for path in _stylesheets():
        css = _BLOCK_COMMENT.sub("", path.read_text(encoding="utf-8"))
        for match in _SVG_DATA_URI.finditer(css):
            opened = css.rindex("{", 0, match.start())
            selectors = css[css.rindex("}", 0, opened) + 1 : opened]
            first = selectors.split(",")[0].strip()
            data = match[3]
            if ";base64" in match[2]:
                svg = base64.b64decode(unquote(data)).decode("utf-8")
            else:
                svg = unquote(data)
            inner = svg[svg.index(">") + 1 : svg.index("</svg>")]
            found[(_relative(path), first)] = _drawing(inner)
    return found


def _block_end(css: str, start: int) -> int:
    """Where the block whose body starts at *start* closes."""
    depth = 1
    at = start
    while depth:
        if css[at] == "{":
            depth += 1
        elif css[at] == "}":
            depth -= 1
        at += 1
    return at


def _selector_list(text: str) -> tuple[str, ...]:
    """A rule's selectors, split at the commas outside a pseudo-class's arguments."""
    parts = [""]
    depth = 0
    for char in text:
        depth += {"(": 1, ")": -1}.get(char, 0)
        if char == "," and depth == 0:
            parts.append("")
        else:
            parts[-1] += char
    return tuple(" ".join(part.split()) for part in parts)


def _forced_colors_inks(css: str) -> tuple[set[str], set[str]]:
    """A stylesheet's selectors that ink a masked glyph, and those forced colors ink CanvasText.

    A selector inks a masked glyph when it sets a background's color on the element and
    pseudo-element a mask is drawn on, in any state: forced colors replace that color with
    Canvas, the ground the glyph sits on.
    """

    def plain(selector: str) -> str:
        return _SELECTOR_STATE.sub("", selector)

    forced_blocks = [
        (match.end(), _block_end(css, match.end())) for match in _FORCED_COLORS.finditer(css)
    ]
    masked: set[str] = set()
    inking: list[tuple[str, ...]] = []
    forced: set[str] = set()
    for rule in _RULE.finditer(css):
        selectors = _selector_list(rule[1])
        ink = _BACKGROUND_COLOR.search(rule[2])
        if any(start <= rule.start(2) < end for start, end in forced_blocks):
            if ink is not None and ink[1].strip() == "CanvasText":
                forced.update(selectors)
            continue
        if _SVG_DATA_URI.search(rule[2]):
            masked.update(plain(selector) for selector in selectors)
        if ink is not None:
            inking.append(selectors)
    inks = {selector for group in inking for selector in group if plain(selector) in masked}
    return inks, forced


def _typed_glyphs() -> dict[str, set[str]]:
    """Each glyph character a browser source types, as itself or as an escape, with its files.

    A comment and a console message are a developer's prose, so their characters are not
    marks a reader sees.
    """
    found: dict[str, set[str]] = {}
    sources = [
        (_relative(path), _script_escapes_decoded(_without_console_messages(_script_code(path))))
        for path in _browser_scripts()
    ]
    sources += [
        (
            _relative(path),
            _css_escapes_decoded(_BLOCK_COMMENT.sub("", path.read_text(encoding="utf-8"))),
        )
        for path in _stylesheets()
    ]
    sources.append(("server.py", _script_escapes_decoded(_shell_template())))
    for name, code in sources:
        for glyph in _GLYPH.findall(code):
            found.setdefault(glyph, set()).add(name)
    return found


def _js_object(text: str, name: str) -> dict[str, str]:
    """The string values of the frozen object literal `name` in *text*."""
    start = text.index(f"const {name} =")
    # The literal's own brace ends its line; a JSDoc type's `{...}` before it does not.
    body = re.search(r"\{\n(.*?)\n\s*\}", text[start:], re.DOTALL)
    assert body is not None, name
    return dict(re.findall(r"(\w+): \"(\w)\"", body[1]))


def _declared_tokens() -> set[str]:
    return {
        token
        for path in _stylesheets()
        for token in _TOKEN_DECLARATION.findall(path.read_text(encoding="utf-8"))
    }


def _rows(source: str) -> list[Row]:
    return [row for row in _catalog() if row.source == source]


def test_every_row_is_well_formed() -> None:
    rows = _catalog()
    assert rows, "the catalog has tables"
    for row in rows:
        assert row.source in SOURCES, f"{row.icon}: {row.source!r} is not a catalog source"
        assert row.kind, f"{row.icon} sits under no kind's heading"
        assert row.meaning, f"{row.icon} says nothing of what it means"
        assert row.defined_in, f"{row.icon} names no file"
        for path in row.defined_in:
            _resolve(path)
        drawn_once = row.source in {
            *DRAWN,
            "CSS mask",
            "Shell",
            "SF Symbol",
            "App glyph",
            "App mark",
        }
        assert not drawn_once or len(row.defined_in) == 1, f"{row.icon} is defined in one place"
    drawn = [(row.icon, row.defined_in) for row in rows if row.source != "Text"]
    assert len(drawn) == len(set(drawn)), "a drawn icon has one row per place it is defined"


def test_the_registry_is_the_catalogs_registry_rows() -> None:
    defined = _svg_definitions(REGISTRY.read_text(encoding="utf-8"))
    rows = _rows("Registry")
    assert {row.defined_in for row in rows} == {("static/icons.js",)}
    assert sorted(row.icon for row in rows) == sorted(defined), (
        "static/icons.js and the catalog's Registry rows name the same glyphs"
    )


def test_every_registry_glyph_has_a_caller_and_every_call_is_a_glyph() -> None:
    """The registry is what its callers ask for: no glyph unused, no name unregistered."""
    defined = set(_svg_definitions(REGISTRY.read_text(encoding="utf-8")))
    used: dict[str, set[str]] = {}
    for path in _browser_scripts():
        if path == REGISTRY:
            continue
        for match in _REGISTRY_USE.finditer(_script_code(path)):
            name = match[1] or match[2]
            if name not in _NOT_GLYPHS:
                used.setdefault(name, set()).add(_relative(path))
    registry = tomllib.loads(TYPE_REGISTRY.read_text(encoding="utf-8"))
    for entry in [*registry["group"], *registry["family"]]:
        if "icon" in entry:
            used.setdefault(entry["icon"], set()).add(_relative(TYPE_REGISTRY))
    assert {name: files for name, files in used.items() if name not in defined} == {}, (
        "a caller asks for a glyph the registry does not have"
    )
    assert sorted(defined - set(used)) == [], "a registry glyph nothing draws"


def test_every_named_svg_outside_the_registry_is_a_row() -> None:
    """A plugin's or a view's own glyph is cataloged where it is defined.

    Every SVG a script draws is one of its named definitions, so a second, unnamed drawing
    in a file that has a named one fails as the first would. The server's page template draws
    none: a glyph the server writes into a page is a root's mark (`source_kind_marks.py`) or
    one of `shell_glyphs.py`'s, and the rest are the registry's.
    """
    defined: set[tuple[str, str]] = set()
    for path in _browser_scripts():
        code = _script_code(path)
        if path == REGISTRY or "<svg" not in code:
            continue
        names = _svg_definitions(path.read_text(encoding="utf-8"))
        assert code.count("<svg") == len(_svg_definitions(code)) == len(names), (
            f"{_relative(path)} draws an SVG it does not define by name"
        )
        defined |= {(_relative(path), name) for name in names}
    assert "<svg" not in _shell_template(), (
        "server.py's page draws an SVG; write one from shell_glyphs.py or use a registry glyph"
    )
    cataloged = {(row.defined_in[0], row.icon) for row in _catalog() if row.source in DRAWN[1:]}
    assert sorted(defined) == sorted(cataloged)


def test_every_glyph_the_servers_code_writes_is_a_shell_row() -> None:
    """A glyph `shell_glyphs.py` holds is a Shell row defined there, under its Lucide id, and
    no browser script or stylesheet holds a second copy of its drawing."""
    source = SHELL_GLYPHS.read_text(encoding="utf-8")
    defined = {name: lucide for lucide, name in _SHELL_GLYPH_DEFINITION.findall(source)}
    assert sorted(defined) == sorted(
        name for name in vars(shell_glyphs) if name.endswith("_SVG")
    ), "every glyph in shell_glyphs.py names its Lucide id in the comment above it"
    rows = [row for row in _rows("Shell") if row.defined_in == ("shell_glyphs.py",)]
    assert {row.icon: row.upstream for row in rows} == defined
    for name in defined:
        drawing: str = getattr(shell_glyphs, name)
        assert drawing.startswith(shell_glyphs.LUCIDE_SVG_OPEN) and drawing.endswith("</svg>")
        elements = drawing.removeprefix(shell_glyphs.LUCIDE_SVG_OPEN).removesuffix("</svg>")
        for path in (*_browser_scripts(), *_stylesheets()):
            assert elements not in path.read_text(encoding="utf-8"), (
                f"{_relative(path)} holds a copy of {name}"
            )


def test_a_plugins_pull_states_draw_the_plugins_glyphs() -> None:
    state = (BUILTIN_PLUGINS / "github" / "pull-state.js").read_text(encoding="utf-8")
    states = dict(re.findall(r"(\w+): Object\.freeze\(\{ icon: \"(\w+)\"", state))
    assert sorted(states.values()) == sorted(_svg_definitions(state))


def test_an_upstream_glyph_is_one_drawing_under_its_own_id() -> None:
    """Rows naming one upstream glyph draw it the same; a commented id is the row's."""
    drawings: dict[str, set[str]] = {}
    masks = _mask_glyphs()
    for row in _catalog():
        if row.source in DRAWN:
            inner, commented = _svg_definitions(_resolve(row.defined_in[0]).read_text("utf-8"))[
                row.icon
            ]
            if commented is not None:
                assert row.upstream == commented, f"{row.icon} is Lucide `{commented}`"
            drawing = _drawing(inner)
        elif row.source == "CSS mask":
            drawing = masks[(row.defined_in[0], row.icon)]
        else:
            continue
        if row.upstream is not None:
            drawings.setdefault(row.upstream, set()).add(drawing)
    forked = {upstream: found for upstream, found in drawings.items() if len(found) > 1}
    assert forked == {}, "one upstream glyph, drawn two ways"


def test_every_masked_glyph_is_a_row() -> None:
    cataloged = {(row.defined_in[0], row.icon) for row in _rows("CSS mask")}
    assert sorted(_mask_glyphs()) == sorted(cataloged)


def test_a_fold_expander_draws_kpress_expand_contract_pair() -> None:
    """A fold's glyphs are KPress's table-of-contents pair, not the chevron a row turns.

    The shell draws them, so a fold outside a rendered document has them too, and they
    are KPress's paths under KPress's ids, so the two products' pair is one mark. The
    weight is the row chevron's, not the sprite's, and this compares paths alone
    (docs/design-system-icons.md, "Where Icons Come From").
    """

    sprite = kpress_adapter.get_kpress_static_asset("icons/icons.svg").content.decode("utf-8")
    kpress = {name: _drawing(inner) for name, inner in _KPRESS_SYMBOL.findall(sprite)}
    masks = _mask_glyphs()
    folds = {row.icon: row for row in _rows("CSS mask") if row.icon.startswith(".fold-expander")}
    assert {icon: row.upstream for icon, row in folds.items()} == _FOLD_GLYPHS
    for icon, upstream in _FOLD_GLYPHS.items():
        assert folds[icon].defined_in == ("static/styles.css",), icon
        assert masks[("static/styles.css", icon)] == kpress[upstream], f"{icon} is not KPress's"
    # The chevron is a row's disclosure, and its row says a fold never takes it.
    toggle = next(row for row in _rows("Registry") if row.icon == "toggle")
    assert "Never a fold expander’s" in toggle.meaning
    assert "fold expanders" not in toggle.meaning


def test_every_masked_glyph_keeps_its_ink_in_forced_colors() -> None:
    """A masked glyph is drawn in its background's color, which forced colors make Canvas.

    That is the ground the glyph sits on, so it would vanish; each selector that inks one
    is drawn again in CanvasText, a system color the mode does not replace
    (docs/design-system-icons.md, "Where Icons Come From").
    """

    shell = (STATIC / "styles.css").read_text(encoding="utf-8")
    shell_inks, _ = _forced_colors_inks(_BLOCK_COMMENT.sub("", shell))
    # The check reaches a glyph's states, not only the rule that masks it.
    assert ".fold-expander:is(:hover, :focus-visible)::before" in shell_inks
    missing: list[str] = []
    for path in _stylesheets():
        css = _BLOCK_COMMENT.sub("", path.read_text(encoding="utf-8"))
        inks, forced = _forced_colors_inks(css)
        missing += [f"{_relative(path)}: {selector}" for selector in sorted(inks - forced)]
    assert missing == [], "a masked glyph is Canvas on Canvas in forced colors"


def test_every_typed_glyph_is_a_text_row_with_the_files_that_type_it() -> None:
    cataloged: dict[str, set[str]] = {}
    for row in _rows("Text"):
        cataloged.setdefault(row.icon, set()).update(row.defined_in)
    assert _typed_glyphs() == cataloged, "a typed glyph and its catalog rows differ"


def test_the_change_letters_are_the_status_tables() -> None:
    """The letters are the changed-files tree's and a diff's, which agree where both speak."""
    tree = _js_object((STATIC / "changed-files-tree.js").read_text("utf-8"), "STATUS_BADGES")
    diff = _js_object(
        (BUILTIN_PLUGINS / "diff" / "diff-model.js").read_text("utf-8"), "KIND_LETTERS"
    )
    shared = set(tree) & set(diff)
    assert shared, "the two tables share statuses"
    assert {status: tree[status] for status in shared} == {s: diff[s] for s in shared}
    rows = _rows("Letter")
    assert sorted(row.icon for row in rows) == sorted(set(tree.values()) | set(diff.values()))
    for row in rows:
        assert set(row.defined_in) == {
            "static/changed-files-tree.js",
            "builtin_plugins/diff/diff-model.js",
        }, row.icon


def test_every_sf_symbol_the_app_draws_is_a_row() -> None:
    """AppKit's `NSImage(systemSymbolName:)`, and SwiftUI's `systemImage:` and `systemName:`."""
    drawn = {
        (_relative(path), name)
        for path in sorted(MACOS_SOURCES.rglob("*.swift"))
        for name in re.findall(
            r'\b(?:systemSymbolName|systemImage|systemName):\s*"([\w.]+)"',
            path.read_text("utf-8"),
        )
    }
    assert sorted(drawn) == sorted((row.defined_in[0], row.icon) for row in _rows("SF Symbol"))


def test_the_type_registrys_shapes_are_cataloged_for_what_takes_them() -> None:
    """A category's or a format's shape is a registry row naming that category or format.

    A file type may look like another file type and like nothing else, so the schema
    permits a group or a family exactly the shapes the type registry gives its categories
    and formats: never a control's glyph, a folder's, or a link's.
    """
    meanings = {row.icon: row.meaning for row in _rows("Registry")}
    registry = tomllib.loads(TYPE_REGISTRY.read_text(encoding="utf-8"))
    shapes: set[str] = set()
    for entry in [*registry["group"], *registry["family"]]:
        if "icon" in entry:
            shapes.add(entry["icon"])
            assert entry["icon"] in meanings, entry["id"]
            assert entry["label"] in meanings[entry["icon"]], (
                f"`{entry['icon']}`'s row does not name {entry['label']}, which takes it"
            )
    schema = json.loads(TYPE_SCHEMA.read_text(encoding="utf-8"))
    for definition in ("family", "group"):
        permitted = schema["$defs"][definition]["properties"]["icon"]["enum"]
        named = sorted(name for name in permitted if name is not None)
        assert named == sorted(shapes), (
            f"the schema lets a {definition} take exactly the shapes file types take"
        )


def test_every_token_a_row_names_is_declared() -> None:
    declared = _declared_tokens()
    for row in _catalog():
        for token in _TOKEN.findall(f"{row.ink} {row.size}"):
            assert token in declared, f"{row.icon}: {token} is declared by no stylesheet"


def test_the_check_reads_a_new_row_and_fails_a_missing_one() -> None:
    """The parser sees what the tables say: a dropped row and an extra one both show."""
    text = CATALOG.read_text(encoding="utf-8")
    rows = _catalog(text)
    toggle = next(row for row in rows if row.icon == "toggle")
    assert toggle.upstream == "chevron-right" and toggle.source == "Registry"
    line = next(line for line in text.splitlines() if line.startswith("| `toggle`"))
    assert "toggle" not in {row.icon for row in _catalog(text.replace(line + "\n", ""))}
    extra = line.replace("`toggle`", "`unheard`", 1)
    assert "unheard" in {row.icon for row in _catalog(text.replace(line, f"{line}\n{extra}"))}


def test_the_check_reads_escapes_and_skips_what_no_reader_sees() -> None:
    """An escaped glyph or mask is still one; a console message or a local `icons` is not."""
    escaped = '"\\u2715" "\\u{1F5C2}" "&rsaquo;" "&#8250;"'
    assert _GLYPH.findall(_script_escapes_decoded(escaped)) == ["✕", "🗂", "›", "›"]
    assert _GLYPH.findall(_css_escapes_decoded('content: "\\203A";')) == ["›"]
    logged = 'console.warn("a → b", f(1), `${"⇢"}`); label = "←";'
    assert _GLYPH.findall(_without_console_messages(logged)) == ["←"]
    calls = "const icons = []; icons.push(1); mb.icons.toggle; sdk()?.icons?.copy;"
    assert [match[1] for match in _REGISTRY_USE.finditer(calls)] == ["toggle", "copy"]
    masks = "url('data:image/svg+xml,%3Csvg%3E%3C/svg%3E') url(data:image/svg+xml;base64,AA==)"
    assert len(_SVG_DATA_URI.findall(masks)) == 2


# ── Source kinds ────────────────────────────────────────────────────

# The one place the ordinary folder is drawn by a script: a folder's view header. A surface that
# draws it for a root fails; one that draws it for another ordinary folder is added here and to
# "The Ordinary Folder" in the catalog together.
ORDINARY_FOLDER_CALLERS = {"static/view-header.js"}
ROOT_MARK_SWIFT = MACOS_SOURCES / "ShellCore" / "Folders" / "RootMark.swift"
# What RootMark names each case of the app's marks: the page's `kind` of root for a root's.
ROOT_MARK_KINDS = {"plainFolder": "folder", "gitCheckout": "git", "mirror": "mirror"}


def _kind_glyphs() -> dict[str, dict[str, str]]:
    """The glyph file's entries, by the `kind` of root each is for."""
    return json.loads(SOURCE_KIND_GLYPHS.read_text(encoding="utf-8"))


def _swift_cases(source: str, start: str, end: str) -> dict[str, str]:
    """The `case .name: "value"` lines of the Swift property from `var start` to `var end`."""
    body = source[source.index(f"var {start}") : source.index(f"var {end}")]
    return dict(re.findall(r'case \.(\w+): "([^"]+)"', body))


def test_the_source_kinds_are_the_identity_routes_kinds_each_with_its_own_glyph() -> None:
    """A root's `kind` has one glyph in the glyph file and one catalog row, and the three
    glyphs and the ordinary folder's are four different drawings."""
    glyphs = _kind_glyphs()
    assert sorted(glyphs) == sorted(get_args(IdentityKind.__value__)), (
        "the glyph file draws each kind of root `/api/identity` says, and no other"
    )
    assert set(KIND_LABELS) == set(glyphs), "every kind of root has its words"
    rows = [row for row in _catalog() if row.kind == "Source Kinds" and row.source == "Shell"]
    assert sorted(row.icon for row in rows) == sorted(g["id"] for g in glyphs.values())
    for kind, glyph in glyphs.items():
        (row,) = (row for row in rows if row.icon == glyph["id"])
        assert row.upstream == glyph.get("lucide")
        assert row.defined_in == ("static/source-kind-glyphs.json",)
        assert f"`{kind}` kind" in row.meaning, f"{row.icon}'s row names the {kind} kind"
    registry = _svg_definitions(REGISTRY.read_text(encoding="utf-8"))
    drawings = {kind: _drawing(glyph["elements"]) for kind, glyph in glyphs.items()}
    drawings["ordinary folder"] = _drawing(registry["folder"][0])
    assert len(set(drawings.values())) == len(drawings), (
        "a source-kind glyph is a different drawing from each other kind's and from `folder`"
    )


def test_the_page_draws_a_root_with_its_server_written_glyph_and_no_script_draws_one() -> None:
    """A root is never drawn as an ordinary folder, and the glyphs are one copy, in the file.

    The server writes the kind's glyph into the page (`tests/test_root_identity.py`), so no
    browser script or stylesheet holds a second copy of one, and the ordinary folder's callers
    are the ones the catalog says.
    """
    callers: dict[str, set[str]] = {}
    for path in _browser_scripts():
        if path == REGISTRY:
            continue
        for match in _REGISTRY_USE.finditer(_script_code(path)):
            callers.setdefault(match[1] or match[2], set()).add(_relative(path))
    assert callers.get("folder", set()) == ORDINARY_FOLDER_CALLERS
    # The root's header draws the navigation's mark, not the ordinary folder: the only place a
    # script reaches `folder` branches on the root (`path !== ""`) and takes the mark first.
    header = (STATIC / "view-header.js").read_text(encoding="utf-8")
    assert 'path !== "" || typeof document === "undefined"' in header
    assert '"#header-root-kind > svg"' in header
    for kind, glyph in _kind_glyphs().items():
        for path in (*_browser_scripts(), *_stylesheets()):
            assert glyph["elements"] not in path.read_text(encoding="utf-8"), (
                f"{_relative(path)} holds a copy of the {kind} glyph"
            )
    assert "source_kind_svg" in (PACKAGE / "server.py").read_text(encoding="utf-8")


def test_the_apps_root_marks_are_the_same_glyphs_and_words_as_the_page() -> None:
    """`RootMark` pairs each kind with the page's glyph and says it in the page's words."""
    swift = ROOT_MARK_SWIFT.read_text(encoding="utf-8")
    glyphs = _kind_glyphs()
    ids = _swift_cases(swift, "glyphID", "label")
    assert {ROOT_MARK_KINDS[case]: ids[case] for case in ROOT_MARK_KINDS} == {
        kind: glyph["id"] for kind, glyph in glyphs.items()
    }, "RootMark.glyphID is the page's glyph for each kind"
    assert ids["folder"] == "folder", "the app's ordinary folder is the registry's `folder`"
    # The app's marks are the catalog's App glyph rows, one for each, the ordinary folder included.
    app_rows = _rows("App glyph")
    assert {row.icon: row.upstream for row in app_rows} == {
        "folder": "folder",
        **{glyph["id"]: glyph.get("lucide") for glyph in glyphs.values()},
    }
    assert {row.defined_in for row in app_rows} == {
        ("apps/macos/Sources/ShellCore/Folders/RootMark.swift",)
    }
    # The words a mark says are `KIND_LABELS`'.
    labels = _swift_cases(swift, "label", "markup")
    assert {
        ROOT_MARK_KINDS[case]: label for case, label in labels.items() if case in ROOT_MARK_KINDS
    } == (dict(KIND_LABELS))
