"""Source checks that the built-in plugin views, and the shell, use the shell's primitives.

Each check is a scan of builtin_plugins/**/*.js (and charts.py) for a pattern the design
system (docs/design-system.md) already forbids, so a plugin cannot quietly redraw what the
shell owns: a button without a control-family class, a hand-formatted number, a failure alert
outside a .notice, or a log kind whose colour differs between the Log and its chart. The
button scan reads the shell's own modules and the server's markup too, since a shell control
that skips the families is as far from them as a plugin's.

Each scan is a heuristic over source text, so every allowlist names its reason.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGINS_DIR = REPO_ROOT / "src" / "metabrowser" / "builtin_plugins"
PLUGIN_JS = tuple(sorted(PLUGINS_DIR.glob("**/*.js")))
STATIC_DIR = REPO_ROOT / "src" / "metabrowser" / "static"
# The shell's modules, not the vendored libraries in static/vendor/, and the server's markup.
SHELL_SOURCES = (*sorted(STATIC_DIR.glob("*.js")), REPO_ROOT / "src" / "metabrowser" / "server.py")

# -- Buttons -------------------------------------------------------------------------------

# The control families of docs/design-system.md, "Control Families", plus the toggle marker
# every disclosure carries.
BUTTON_PRIMITIVES = frozenset(
    {
        "btn",
        "icon-btn",
        "chip",
        # "Filter Controls": the chip family's quiet reset, a variant of the chip.
        "chip-clear",
        "tab-btn",
        "menu-item",
        "menu-seg",
        "section-disclosure-trigger",
        "fold-expander",
        "disclosure-toggle",
    }
)

# A button whose class is not a primitive, and why that is right.
BUTTON_CLASS_ALLOWLIST = {
    # "A text action ... on <a> and <button> alike": each context names its own class.
    "github-pull-text-action": "the pull page's text action, a link-like action in a line of chrome",
    # A sortable column header's label: a text action in a line of chrome, with `aria-sort` on
    # its cell, since a bordered button in a header would read as a different thing.
    "agents-sort": "the session table's sortable column headers",
    # The file bar is itself the .disclosure-toggle row; this button is its labelled hit area.
    "diff-file-toggle": "the label of a diff file bar, which carries .disclosure-toggle",
    "diff-file-view": "the diff file’s quiet text action, also used as a link",
    # A table's header: its label sorts, and its ▾ opens the column's menu, in the header's
    # label type (docs/design-system.md, "Data Tables").
    "table-sort": "a sortable column's header label, which sorts it",
    "table-head-menu": "a column header's menu trigger",
    # A guide's step list is a table of contents of its steps, in the description's text
    # size; `.menu-item` is a menu's row at the controls' size (docs/design-system.md,
    # "Guided Review").
    "github-pull-guide-steps-link": "a Guided Review step list row, which goes to its step",
}

# A shell button whose class is not a primitive, and why that is right. Each is a control of
# its own surface, documented at its rule in docs/design-system.md, and none redraws a family.
SHELL_BUTTON_CLASS_ALLOWLIST = {
    # "View Headers": a crumb of the eyebrow's path is a step of a path, not a button's box.
    "folder-crumb": "a view header's folder crumb",
}

_QUOTED = re.compile(r"""(["'\x60])((?:\\.|(?!\1).)*)\1""", re.DOTALL)
_TAG_CLASS = re.compile(r"""class=["']([^"']*)["']""")
_FACTORY_BUTTON = re.compile(r"""\b(?:h|el)\(\s*["']button["']\s*,""")
_CREATED_BUTTON = re.compile(r"""(\w+)\s*=\s*[\w.]*createElement\(\s*["']button["']\s*\)""")


def _tokens(text: str) -> set[str]:
    """Class-like words in every string literal of the text."""
    found: set[str] = set()
    for match in _QUOTED.finditer(text):
        found.update(re.findall(r"[A-Za-z][\w-]*", match.group(2)))
    return found


# A helper that gives the element it is handed its family's class, by what it sets: the SDK's
# menu rows (`renderLinkMenuItem` in static/plugin-sdk-views.js sets `menu-item`).
_CLASS_HELPERS = {"renderLinkMenuItem": frozenset({"menu-item"})}


def _assigned_class(variable: str, window: str) -> set[str]:
    """The class words a created element is given in the statements after its creation."""
    pattern = (
        rf"\b{variable}\.(?:className\s*=|classList\.add\(|setAttribute\(\s*[\"']class[\"']\s*,)"
        r"([^;]*);"
    )
    assigned = re.search(pattern, window)
    if assigned:
        return _tokens(assigned.group(1))
    for helper, words in _CLASS_HELPERS.items():
        if re.search(rf"\b{helper}\(\s*{variable}\s*,", window):
            return set(words)
    return set()


def _button_class_tokens(
    paths: tuple[Path, ...] = PLUGIN_JS,
) -> list[tuple[str, int, set[str]]]:
    """(file, line, class words) for each button the sources build."""
    out: list[tuple[str, int, set[str]]] = []
    for path in paths:
        source = path.read_text()
        where = str(path.relative_to(REPO_ROOT))

        def line_of(index: int, source: str = source) -> int:
            return source.count("\n", 0, index) + 1

        # Markup: the tag's own class attribute.
        for match in re.finditer(r"<button\b", source):
            tag = source[match.start() : source.find(">", match.start())]
            klass = _TAG_CLASS.search(tag)
            # Words, not whitespace runs: the server's f-string markup puts a `{...}` inside
            # the attribute, as `class="tab-btn{active}"` does.
            words = set(re.findall(r"[A-Za-z][\w-]*", klass.group(1))) if klass else set()
            out.append((where, line_of(match.start()), words))
        # h("button", {class: "..."}) and el("button", "...").
        for match in _FACTORY_BUTTON.finditer(source):
            window = source[match.end() : match.end() + 220]
            out.append((where, line_of(match.start()), _tokens(window)))
        # const x = ...createElement("button"): the class assigned to x afterward.
        for match in _CREATED_BUTTON.finditer(source):
            window = source[match.end() : match.end() + 1200]
            out.append((where, line_of(match.start()), _assigned_class(match.group(1), window)))
    return out


def test_every_plugin_button_carries_a_control_family_class() -> None:
    buttons = _button_class_tokens()
    assert len(buttons) >= 15, "the scan found too few buttons; its patterns no longer match"
    allowed = BUTTON_PRIMITIVES | set(BUTTON_CLASS_ALLOWLIST)
    offenders = [
        f"{where}:{line} builds a button with classes {sorted(words) or 'none'}"
        for where, line, words in buttons
        if not words & allowed
    ]
    assert not offenders, (
        "a plugin button must carry a control-family primitive (docs/design-system.md, "
        "'Control Families'):\n  " + "\n  ".join(offenders)
    )


def test_every_shell_button_carries_a_control_family_class() -> None:
    """The plugins' rule, for the shell's own modules and the server's markup.

    The scan reads the three forms `_button_class_tokens` knows. A button whose tag is chosen
    at run time, as the shortcut strip's hint and a commit's changed-file row are, is not
    read, and so is not listed.
    """

    buttons = _button_class_tokens(SHELL_SOURCES)
    assert len(buttons) >= 25, "the scan found too few buttons; its patterns no longer match"
    allowed = BUTTON_PRIMITIVES | set(SHELL_BUTTON_CLASS_ALLOWLIST)
    offenders = [
        f"{where}:{line} builds a button with classes {sorted(words) or 'none'}"
        for where, line, words in buttons
        if not words & allowed
    ]
    assert not offenders, (
        "a shell button must carry a control-family primitive (docs/design-system.md, "
        "'Control Families'), or be named with its reason in SHELL_BUTTON_CLASS_ALLOWLIST:"
        "\n  " + "\n  ".join(offenders)
    )
    # An allowance nothing uses any more is a stale reason: take it out.
    used = set().union(*(words for _, _, words in buttons))
    assert not set(SHELL_BUTTON_CLASS_ALLOWLIST) - used, set(SHELL_BUTTON_CLASS_ALLOWLIST) - used


# -- Numbers -------------------------------------------------------------------------------

# Intl.NumberFormat and toLocaleString where the SDK has formatInteger and formatFileCount.
NUMBER_FORMAT_ALLOWLIST = {
    "folder/file-type-summary-model.js": "percentages with a fraction digit; the SDK has no formatter",
}

# One line elsewhere that may format a number itself, by pattern: the fallback for a module
# driven without the shell's formatters.
NUMBER_FORMAT_LINE_ALLOWLIST = {
    "diff/diff-view.js": re.compile(
        r"const fallback = new Intl\.NumberFormat\(undefined, \{ maximumFractionDigits: 0 \}\);"
    ),
}


def test_plugins_format_numbers_with_the_sdk() -> None:
    offenders: list[str] = []
    for path in PLUGIN_JS:
        relative = str(path.relative_to(PLUGINS_DIR))
        if relative in NUMBER_FORMAT_ALLOWLIST:
            continue
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            allowed = NUMBER_FORMAT_LINE_ALLOWLIST.get(relative)
            if allowed and allowed.search(line):
                continue
            if re.search(r"toLocaleString\(|Intl\.NumberFormat\(", line):
                offenders.append(f"{relative}:{number}: {line.strip()}")
    assert not offenders, (
        "format numbers with mb.formatInteger / mb.formatFileCount, so every count wears one "
        "grouping:\n  " + "\n  ".join(offenders)
    )
    for relative in NUMBER_FORMAT_ALLOWLIST:
        source = (PLUGINS_DIR / relative).read_text()
        assert "Intl.NumberFormat(" in source, f"{relative} no longer needs its allowlist entry"
    for relative, pattern in NUMBER_FORMAT_LINE_ALLOWLIST.items():
        source = (PLUGINS_DIR / relative).read_text()
        assert pattern.search(source), f"{relative} no longer needs its line allowlist entry"


# -- Alerts --------------------------------------------------------------------------------

ALERT_ROLE = re.compile(
    r"""role=["']alert["']|["']role["']\s*,\s*["']alert["']|role:\s*["']alert["']"""
)
# A class assignment, as markup, `className =`, or `setAttribute("class", ...)`, whose value has
# the `notice` word, or `setStatusNotice(el, ...)`, which sets it: a variable or a comment
# named `notice` does not count.
NOTICE_CLASS = re.compile(
    r"""setStatusNotice\(|(?:class(?:Name)?\s*=\s*|setAttribute\(\s*["']class["']\s*,\s*)\\?["'\x60][^"'\x60]*"""
    r"""(?<![\w-])notice(?![\w-])"""
)
ERROR_SEVERITY = re.compile(
    r"""setStatusNotice\([^,()]+,\s*["']error["']|data-severity=\\?["']error["']|["']data-severity["']\s*,\s*["']error["']"""
)

# A file whose alert is not a notice box, and why. None today.
ALERT_ALLOWLIST: dict[str, str] = {}


def test_role_alert_sits_on_a_notice() -> None:
    """An alert says something failed, which is what a notice with a severity is for."""
    offenders: list[str] = []
    seen = 0
    for path in PLUGIN_JS:
        source = path.read_text()
        relative = str(path.relative_to(PLUGINS_DIR))
        for match in ALERT_ROLE.finditer(source):
            seen += 1
            # The element's own markup, or the lines that build it.
            window = source[max(0, match.start() - 400) : match.end() + 300]
            if NOTICE_CLASS.search(window) or relative in ALERT_ALLOWLIST:
                continue
            line = source.count("\n", 0, match.start()) + 1
            offenders.append(f"{relative}:{line}")
    assert seen >= 4, "the scan found too few alerts; its pattern no longer matches the code"
    assert not offenders, 'role="alert" belongs on a .notice with a severity:\n  ' + "\n  ".join(
        offenders
    )


def test_an_error_notice_is_an_alert() -> None:
    """Screen readers interrupt for an error severity; `status` is for the warning case."""
    offenders: list[str] = []
    seen = 0
    for path in PLUGIN_JS:
        source = path.read_text()
        for match in ERROR_SEVERITY.finditer(source):
            seen += 1
            window = source[max(0, match.start() - 400) : match.end() + 300]
            if not ALERT_ROLE.search(window):
                line = source.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.relative_to(PLUGINS_DIR)}:{line}")
    assert seen >= 4, "the scan found too few error notices; its pattern no longer matches"
    assert not offenders, 'data-severity="error" needs role="alert":\n  ' + "\n  ".join(offenders)


# -- Agent-log kind hues -------------------------------------------------------------------

AGENT_LOG_CSS = PLUGINS_DIR / "agents" / "agent-log.css"
CHARTS_PY = REPO_ROOT / "src" / "metabrowser" / "builtin_plugins" / "agents" / "charts.py"
# How far apart two hues of one kind may sit, in degrees: the chart's tool result is a
# lighter step of the badge's amber, not the same value.
HUE_TOLERANCE = 20
NEUTRAL_CHROMA = 0.04
# Each chart kind's badge: the Log's ink variable for it, per agents/agent-log.css.
BADGE_INK = {
    "tool_call": "--agent-kind-tool-call-text",
    "tool_result": "--agent-kind-tool-result-text",
    "text": "--agent-kind-text-text",
    "thinking": "--agent-kind-thinking-text",
    "result": "--agent-kind-metering-text",
    "init": "--agent-kind-context-text",
    "system": "--agent-kind-control-text",
}


def _theme_blocks() -> tuple[str, str]:
    css = re.sub(r"/\*.*?\*/", "", AGENT_LOG_CSS.read_text(), flags=re.DOTALL)
    light = re.search(r":root\s*\{(.*?)\}", css, re.DOTALL)
    dark = re.search(r'\[data-theme="dark"\]\s*\{(.*?)\}', css, re.DOTALL)
    assert light
    assert dark
    return light.group(1), dark.group(1)


def _oklch(block: str, name: str) -> tuple[float, float]:
    """(chroma, hue) of an oklch() custom property."""
    pattern = rf"{re.escape(name)}:\s*oklch\(([\d.]+)%\s+([\d.]+)\s+([\d.]+)\)"
    match = re.search(pattern, block)
    assert match, f"{name} is not an oklch() value in agents/agent-log.css"
    return float(match.group(2)), float(match.group(3))


def _chart_variables() -> dict[str, str]:
    source = CHARTS_PY.read_text()
    block = re.search(r"kind_colors = \{(.*?)\}", source, re.DOTALL)
    assert block, "charts.py no longer maps event kinds to colours in kind_colors"
    return dict(re.findall(r'"(\w+)":\s*"var\((--[\w-]+)\)"', block.group(1)))


def _hue_distance(a: float, b: float) -> float:
    return min(abs(a - b), 360 - abs(a - b))


def test_agent_log_kind_has_one_hue_in_the_log_and_its_chart() -> None:
    chart = _chart_variables()
    assert set(chart) == set(BADGE_INK), "the chart and the badges disagree on which kinds exist"
    for block in _theme_blocks():
        for kind, badge in BADGE_INK.items():
            badge_chroma, badge_hue = _oklch(block, badge)
            chart_chroma, chart_hue = _oklch(block, chart[kind])
            if badge_chroma < NEUTRAL_CHROMA or chart_chroma < NEUTRAL_CHROMA:
                assert badge_chroma < NEUTRAL_CHROMA
                assert chart_chroma < NEUTRAL_CHROMA, f"{kind}: only one of the two is neutral"
            else:
                assert _hue_distance(badge_hue, chart_hue) <= HUE_TOLERANCE, (
                    f"{kind}: the chart's hue {chart_hue} is not the badge's {badge_hue}"
                )


def test_agent_log_badges_use_the_shared_badge_primitive() -> None:
    source = (PLUGINS_DIR / "agents" / "agent-log.js").read_text()
    assert 'class="file-header-badge log-event-kind' in source
    css = AGENT_LOG_CSS.read_text()
    rule = re.search(r"\.log-event-kind\s*\{(.*?)\}", css, re.DOTALL)
    assert rule
    for prop in ("padding", "font-size", "font-weight", "border-radius", "white-space"):
        assert prop not in rule.group(1), f".log-event-kind restates the badge primitive's {prop}"
