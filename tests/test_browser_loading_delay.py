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
        "folder totals": PLUGIN_ROOT / "folder" / "folder-totals.js",
        "Treemap": PLUGIN_ROOT / "folder" / "treemap.js",
        "file types": PLUGIN_ROOT / "folder" / "distribution-view.js",
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

    Every unexpanded folder past the server's depth cap carries a lazy stub, so
    the sweep takes its candidates from the rendered tree rather than guessing.
    Which of those stubs is a candidate is a question about the screen, and
    ``tests/dom/subtree-prefetch-viewport-behavior.js`` owns that half.
    """

    app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    assert "data-tree-lazy-stub" in app
    sweep = app[app.index("function pendingSubtreePaths()") :]
    sweep = sweep[: sweep.index("function isNearNavViewport(")]
    assert 'querySelectorAll("[data-tree-lazy-stub]")' in sweep
    # Already cached or already being fetched are both "no request needed".
    assert "subtreeCache.has(key)" in sweep
    assert "subtreeRequests.has(key)" in sweep

    # Warming the tree must never compete with the request a reader is waiting
    # on: bounded lanes, a bounded sweep, and — for the speculative sweep —
    # only while the browser is idle. The sweep a reader asks for by opening a
    # folder is not speculative and runs on a timer instead; the DOM shim owns
    # that distinction.
    assert "SUBTREE_PREFETCH_MAX_CONCURRENT" in app
    assert "SUBTREE_PREFETCH_MAX_PER_SWEEP" in app
    schedule = app[app.index("function scheduleSubtreePrefetch(options)") :][:900]
    assert "requestIdleCallback" in schedule


def test_a_click_joins_an_in_flight_prefetch_instead_of_refetching() -> None:
    """Otherwise the prefetch makes the very expansion it exists to speed up
    cost two identical requests."""

    app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    fetch_block = app[
        app.index("function fetchSubtree(path)") : app.index("async function loadSubtree(")
    ]

    assert "const existing = subtreeRequests.get(key)" in fetch_block
    assert "return existing" in fetch_block
    assert "subtreeRequests.set(key, request)" in fetch_block
    # The entry is dropped on both settle paths, or one failure would pin a
    # rejected promise as the answer for that folder forever.
    assert "request.then(forget, forget)" in fetch_block


def test_shell_shares_immediate_claim_owned_preview_feedback() -> None:
    app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    css = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")
    select_file = app[
        app.index("async function selectFile(path, preferredViewId)") : app.index(
            "// ── File rendering"
        )
    ]

    begin = app[app.index("function beginPreviewNavigation") :][:900]
    end = app[app.index("function endPreviewNavigation") :][:700]
    assert 'preview.classList.add("preview-navigation-pending")' in begin
    assert 'preview.setAttribute("aria-busy", "true")' in begin
    assert "data-preview-pending-claim" in begin
    assert "isPreviewClaimCurrent(claim)" in begin
    assert "clearPreviewNavigationState(preview);" in end
    clear = app[app.index("function clearPreviewNavigationState") :][:500]
    assert 'preview.classList.remove("preview-navigation-pending")' in clear
    assert 'preview.removeAttribute("aria-busy")' in clear

    assert "var LOADING_INDICATOR_DELAY_MS = 120;" in app
    assert "var retainedPreview = beginPreviewNavigation(previewClaim);" in select_file
    assert select_file.index("beginPreviewNavigation(previewClaim)") < select_file.index(
        "loadingIndicatorTimer = setTimeout"
    )
    assert "if (!retainedPreview)" in select_file

    assert "--preview-navigation-pending-opacity:" in css
    shared_rule = css[css.index("#preview-pane.preview-navigation-pending") :][:600]
    assert "opacity: var(--preview-navigation-pending-opacity);" in shared_rule
    assert "transition: opacity var(--transition-fast);" in shared_rule
    reduced = css[css.index("@media (prefers-reduced-motion: reduce)") :]
    assert "#preview-pane.preview-navigation-pending" in reduced
    assert "transition: none;" in reduced


def test_git_commit_staging_has_one_shell_owned_atomic_handoff() -> None:
    app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    git = (STATIC_ROOT / "git-panel.js").read_text(encoding="utf-8")
    diff = (PLUGIN_ROOT / "diff" / "index.js").read_text(encoding="utf-8")

    node_seam = app[app.index("function renderPreviewNode") :][:500]
    assert "disposeActivePluginViews()" in node_seam
    assert "preview.replaceChildren(node)" in node_seam

    select = git[git.index("async function selectCommit") : git.index("function renderFileRow")]
    assert "disposeCommitDiff();" not in select[: select.index("await preparation.detail")]
    assert "prepareRevision(revision, false)" in select
    assert "renderPreviewNode(stage, previewClaim)" in select
    assert select.index("beginDiffPreparation") < select.index("renderPreviewNode")
    assert "ctx.raw === undefined" in diff
    assert "showSummary: !revision" in diff
