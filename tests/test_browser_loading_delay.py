"""Structural checks for flicker-free transient loading states."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_ROOT = REPO_ROOT / "src" / "metabrowser" / "static"
PLUGIN_ROOT = REPO_ROOT / "src" / "metabrowser" / "builtin_plugins"


def test_transient_loading_utility_has_a_short_quiet_period() -> None:
    css = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")

    assert "--loading-state-delay: 50ms;" in css
    start = css.index(".mb-delayed-loading {")
    block = css[start : start + 300]
    assert "visibility: hidden;" in block
    assert (
        "animation: mb-delayed-loading-reveal 0s linear var(--loading-state-delay) forwards;"
        in block
    )
    assert "@keyframes mb-delayed-loading-reveal" in css
    assert "visibility: visible;" in css[css.index("@keyframes mb-delayed-loading-reveal") :][:200]


def test_every_fast_renderer_uses_the_delayed_loading_utility() -> None:
    sources = {
        "shell": STATIC_ROOT / "app.js",
        "Markdown": PLUGIN_ROOT / "markdown" / "rendered.js",
        "folder Overview": PLUGIN_ROOT / "folder" / "overview.js",
        "Treemap": PLUGIN_ROOT / "folder" / "treemap.js",
        "agent-log charts": PLUGIN_ROOT / "agent_log" / "index.js",
    }

    for label, path in sources.items():
        source = path.read_text(encoding="utf-8")
        assert "mb-delayed-loading" in source, f"{label} exposes an immediate loading flash"


def test_no_spinner_is_painted_outside_the_quiet_period() -> None:
    """Every spinner in a rendered string carries the delay utility.

    The file-level check above passes as soon as a module uses the utility
    anywhere, which is how the lazy subtree placeholders flashed on every
    expansion while `app.js` was already "covered". A spinner is the one piece
    of loading chrome with no reason to exist before the quiet period, so each
    one is checked where it is written.
    """

    for label, path in {
        "shell": STATIC_ROOT / "app.js",
        "Markdown": PLUGIN_ROOT / "markdown" / "rendered.js",
    }.items():
        source = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(source.splitlines(), start=1):
            if 'class="spinner' not in line:
                continue
            # The spinner sits inside a wrapper that carries the utility, so the
            # window is the few lines around it rather than the line itself.
            window = "\n".join(source.splitlines()[max(0, line_number - 4) : line_number + 2])
            assert "mb-delayed-loading" in window, (
                f"{label}:{line_number} paints a spinner with no quiet period"
            )


def test_the_screen_reader_only_class_is_defined_for_every_surface() -> None:
    """`sr-only` has to hide text everywhere, or it only looks hidden.

    This class was defined once, scoped to the folder tables' own stylesheet,
    which is loaded as a plugin's extra styles. Markup outside those two
    ancestors matched no rule at all, so a label moved into an `sr-only` span
    to get it out of sight went on printing verbatim — the shell, the Markdown
    renderer, and the Treemap all read "Loading …" in plain text. A scoped
    definition passes every check that greps for the class name, so pin the
    definition itself, in the stylesheet every surface loads.
    """

    css = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")

    start = css.index(".sr-only {")
    block = css[start : css.index("}", start)]
    assert "position: absolute;" in block
    assert "clip: rect(0, 0, 0, 0);" in block
    assert "width: 1px;" in block and "height: 1px;" in block

    # A plugin redefining it would drift from this one; there is no reason for
    # a second copy now that the shared stylesheet carries it.
    for stylesheet in PLUGIN_ROOT.rglob("*.css"):
        text = stylesheet.read_text(encoding="utf-8")
        assert ".sr-only {" not in text, f"{stylesheet.name} redefines the shared sr-only"


def test_spinners_carry_no_visible_loading_label() -> None:
    """A spinner plus "Loading X…" says the same thing twice.

    The surface being replaced already says what is loading, so the label is
    screen-reader-only. States a spinner cannot express on its own (a scan
    still running, say) keep their visible copy.
    """

    sources = {
        "shell": STATIC_ROOT / "app.js",
        "server shell": REPO_ROOT / "src" / "metabrowser" / "server.py",
        "Markdown": PLUGIN_ROOT / "markdown" / "rendered.js",
        "agent-log charts": PLUGIN_ROOT / "agent_log" / "index.js",
        "folder totals": PLUGIN_ROOT / "folder" / "folder_totals.js",
        "Treemap": PLUGIN_ROOT / "folder" / "treemap.js",
        "file types": PLUGIN_ROOT / "folder" / "distribution_view.js",
    }
    # "Still scanning this folder…" and the tooltip's "Loading size…" are not
    # in this set: they report a state a spinner cannot express on its own.
    generic = ("Loading file…", "Loading document…", "Loading folder…", "Loading files…")
    generic += ("Loading charts…", "Loading treemap…", "Loading file totals…")
    generic += ("Loading file types…",)

    for label, path in sources.items():
        source = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(source.splitlines(), start=1):
            for phrase in generic:
                if phrase not in line:
                    continue
                window = "\n".join(source.splitlines()[max(0, line_number - 3) : line_number + 1])
                assert "sr-only" in window, (
                    f"{label}:{line_number} shows a visible {phrase!r} beside a spinner"
                )


def test_expandable_folders_are_prefetched_so_expansion_needs_no_load() -> None:
    """The fastest loading state is the one that never runs.

    Every unexpanded folder past the server's depth cap carries a lazy stub,
    which is exactly the set a reader can open next, so the sweep takes its
    candidates from the rendered tree rather than guessing.
    """

    app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    assert "data-tree-lazy-stub" in app
    sweep = app[app.index("function pendingSubtreePaths()") :]
    sweep = sweep[: sweep.index("function scheduleSubtreePrefetch()")]
    assert 'querySelectorAll("[data-tree-lazy-stub]")' in sweep
    # Already cached or already being fetched are both "no request needed".
    assert "!subtreeCache.has(path)" in sweep
    assert "!subtreeRequests.has(path)" in sweep

    # Warming the tree must never compete with the request a reader is waiting
    # on: bounded lanes, a bounded sweep, and only while the browser is idle.
    assert "SUBTREE_PREFETCH_MAX_CONCURRENT" in app
    assert "SUBTREE_PREFETCH_MAX_PER_SWEEP" in app
    schedule = app[app.index("function scheduleSubtreePrefetch()") :][:600]
    assert "requestIdleCallback" in schedule


def test_a_click_joins_an_in_flight_prefetch_instead_of_refetching() -> None:
    """Otherwise the prefetch makes the very expansion it exists to speed up
    cost two identical requests."""

    app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    fetch_block = app[
        app.index("function fetchSubtree(path)") : app.index("async function loadSubtree(")
    ]

    assert "const existing = subtreeRequests.get(path)" in fetch_block
    assert "return existing" in fetch_block
    assert "subtreeRequests.set(path, request)" in fetch_block
    # The entry is dropped on both settle paths, or one failure would pin a
    # rejected promise as the answer for that folder forever.
    assert "request.then(forget, forget)" in fetch_block


def test_shell_keeps_the_previous_preview_during_fast_fetches() -> None:
    app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    select_file = app[
        app.index("async function selectFile(path, preferredViewId)") : app.index(
            "// ── File rendering"
        )
    ]

    assert "var LOADING_INDICATOR_DELAY_MS = 120;" in app
    assert select_file.index("loadingIndicatorTimer = setTimeout") < select_file.index(
        "preview.innerHTML"
    )
