"""The app.js seams the shell keymap reaches its controls through.

``static/shell-keymap.js`` gives the view tabs, the header's Up and Copy, the filters,
and the branch switcher their keys, and ``tests/dom/key-reveal-session.js`` runs it with
the production registry. What a key does there is an activation path that app.js owns:
each runs what a click runs, through a named function a click shares, and never by
synthesizing the click. ``app.js`` is a legacy module no session loads whole, so these
checks pin where those paths and calls sit, as ``tests/test_quick_file_integration.py``
pins the quick-file seams.
"""

from __future__ import annotations

from metabrowser import server as proc_browser


def _read_app_js() -> str:
    return proc_browser.STATIC_DIR.joinpath("app.js").read_text()


def _function_source(js: str, name: str) -> str:
    """One top-level function's source, up to the next column-zero definition."""

    start = js.index(f"function {name}(")
    end = js.find("\nfunction ", start + 1)
    return js[start:] if end == -1 else js[start:end]


def test_a_view_tab_is_selected_by_one_path_the_click_and_the_key_share() -> None:
    js = _read_app_js()
    select = _function_source(js, "selectPreviewTab")
    assert 'b.setAttribute("aria-selected", on ? "true" : "false")' in select
    assert "setActivePreviewView(tabId, container)" in select
    assert "_metabrowserMount" in select
    assert ".focus(" not in select

    init = _function_source(js, "initTabs")
    assert "selectPreviewTab(bar, btn.dataset.tab)" in init
    show = _function_source(js, "showPreviewTab")
    assert "selectPreviewTab(bar, tabId)" in show
    assert ".click()" not in show


def test_the_view_tab_bar_is_a_tablist_carrying_each_declared_key() -> None:
    render = _function_source(_read_app_js(), "renderFile")
    assert '<div class="tab-bar" role="tablist">' in render
    assert 'role="tab" aria-selected="' in render
    assert "data-view-key=" in render


def test_a_filter_key_opens_its_menu_through_the_triggers_path() -> None:
    js = _read_app_js()
    init = _function_source(js, "initFilterBar")
    assert "onMenuToggle: toggleFilterMenu," in init
    open_menu = _function_source(js, "openFilterMenu")
    assert "toggleFilterMenu(key, true)" in open_menu
    assert '.chip-menu-item[aria-checked="true"]' in open_menu
    assert "row.focus()" in open_menu
    assert ".click()" not in open_menu


def test_the_branch_switcher_handle_is_kept() -> None:
    start = _function_source(_read_app_js(), "startSourceRefSelector")
    assert "sourceRefSelector = window.MetabrowserSourceRefSelector?.mount(element)" in start


def test_the_files_tab_hands_focus_to_the_tree_read_when_called() -> None:
    attach = _function_source(_read_app_js(), "attachMainTabs")
    assert "focusFilesRow: () => treeKeyboard?.focusCurrent() ?? false" in attach


def test_the_view_tab_letters_follow_only_a_committed_bar() -> None:
    """``commitViewTabs`` runs inside view composition's ``commit()``, never while staging.

    A stage that is cancelled, as a main tab switch abandons a file load, must have
    registered nothing, or it would take the letters of the bar still on screen; and
    ``cancel()`` runs the staged disposers too, so the keymap pushes nothing into them.
    """

    render = _function_source(_read_app_js(), "renderFile")
    commit_start = render.index("stagedPluginLifecycle.commit(() => {")
    commit_end = render.index("})", commit_start)
    commit = render[commit_start:commit_end]
    replaced = commit.index("preview.replaceChildren(...replacementNodes);")
    committed = commit.index(
        "shellKeymap?.commitViewTabs(previousBar, committedViewTabBar(preview));"
    )
    assert commit.index("const previousBar = committedViewTabBar(preview);") < replaced < committed
    assert render.count("commitViewTabs") == 1
    assert "shellKeymap" not in render[:commit_start]
    assert "stagedPluginDisposers.push" not in render


def test_every_main_pane_install_brings_the_keys_along() -> None:
    finish = _function_source(_read_app_js(), "finishRetainedPullPage")
    assert "shellKeymap?.syncViewTabs(committedViewTabBar());" in finish
    assert "shellKeymap?.syncHeader();" in finish


def test_the_keyboard_infrastructure_owns_the_reveal_and_the_keymap() -> None:
    js = _read_app_js()
    init = _function_source(js, "initKeyboardInfrastructure")
    assert "MetabrowserShellKeymap.createShellKeymap({" in init
    assert "shell: shellKeymapShell()," in init
    assert "MetabrowserKeyReveal.createKeyReveal({" in init
    dispose = _function_source(js, "disposeKeyboardInfrastructure")
    assert dispose.index("keyReveal?.dispose();") < dispose.index("shortcutRegistry?.dispose();")
    assert dispose.index("shellKeymap?.dispose();") < dispose.index("shortcutRegistry?.dispose();")


def test_header_controls_are_read_from_the_committed_pane_and_anchor_their_badges() -> None:
    js = _read_app_js()
    controls = _function_source(js, "committedHeaderControls")
    assert '".folder-up[data-nav-dir]:not([disabled])"' in controls
    assert '".folder-breadcrumb [data-nav-dir]"' in controls
    assert '".file-header-copy"' in controls
    assert "headerCopyBridge" in controls
    assert '<div class="file-header folder-header" data-kbd-badge-anchor>' in js
    assert '<div class="file-header" data-kbd-badge-anchor>' in js
    filters = _function_source(js, "renderNavFilterBar")
    assert filters.index("bar.innerHTML = main + drawer;") < filters.index(
        "shellKeymap?.syncFilters();"
    )


def test_the_commit_view_lends_its_copy_revision_through_the_bridge() -> None:
    panel = proc_browser.STATIC_DIR.joinpath("git-panel.js").read_text()
    assert "bridge.attachHeaderCopy?.(revisionCopy)" in panel
    assert '<div class="git-commit-header" data-kbd-badge-anchor>' in panel
