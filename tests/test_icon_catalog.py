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
- the type registry's shapes are cataloged and named for the categories and formats that
  take them, and its schema permits exactly those shapes;
- each token a row's ink or size names is declared by a shipped stylesheet.

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
from typing import NamedTuple
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE = REPO_ROOT / "src" / "metabrowser"
STATIC = PACKAGE / "static"
BUILTIN_PLUGINS = PACKAGE / "builtin_plugins"
CATALOG = REPO_ROOT / "docs" / "design-system-icons.md"
REGISTRY = STATIC / "icons.js"
TYPE_REGISTRY = PACKAGE / "data" / "file-rollup-format" / "recommended-file-types.toml"
TYPE_SCHEMA = PACKAGE / "data" / "file-rollup-format" / "file-type-registry.schema.json"
MACOS_SOURCES = REPO_ROOT / "apps" / "macos" / "Sources"

HEADER = ("Icon", "Source", "Meaning", "Defined in", "Ink", "Size")
# The sources a row may name, by what defines its drawing.
DRAWN = ("Registry", "Plugin", "View bundle")
SOURCES = frozenset({*DRAWN, "CSS mask", "Text", "Letter", "SF Symbol", "App glyph", "App mark"})

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
        drawn_once = row.source in {*DRAWN, "CSS mask", "SF Symbol", "App glyph", "App mark"}
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
    in a file that has a named one fails as the first would. The server's page draws none:
    the shell's glyphs are the registry's, which it loads before its first paint.
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
        "server.py's page draws an SVG; draw a registry glyph instead"
    )
    cataloged = {(row.defined_in[0], row.icon) for row in _catalog() if row.source in DRAWN[1:]}
    assert sorted(defined) == sorted(cataloged)


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
