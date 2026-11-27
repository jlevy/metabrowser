"""The app.js seams the shell keymap reaches its controls through.

``static/shell-keymap.js`` gives the view tabs, the header's Up, and the branch switcher
their letters and the filters their numbers, and ``tests/dom/key-reveal-session.js`` runs it with
the production registry. What a key does there is an activation path that app.js owns:
each runs what a click runs, through a named function a click shares, and never by
synthesizing the click. ``app.js`` is a legacy module no session loads whole, so these
checks pin where those paths and calls sit, as ``tests/test_quick_file_integration.py``
pins the quick-file seams.
"""

from __future__ import annotations

import asyncio
import re

from metabrowser import server as proc_browser
from tests.shell_request import shell_request


def _read_app_js() -> str:
    return proc_browser.STATIC_DIR.joinpath("app.js").read_text()


def _function_source(js: str, name: str) -> str:
    """One top-level function's source, up to the next column-zero definition."""

    start = js.index(f"function {name}(")
    end = js.find("\nfunction ", start + 1)
    return js[start:] if end == -1 else js[start:end]


def _read_view_header_js() -> str:
    return proc_browser.STATIC_DIR.joinpath("view-header.js").read_text()


def _view_tab_markup() -> str:
    composition = proc_browser.STATIC_DIR.joinpath("view-composition.js").read_text()
    start = composition.index("  function renderTabs(")
    return composition[start : composition.index("\n  }\n", start)]


def _builder_source(js: str, name: str) -> str:
    """One of view-header.js's builders, up to the next builder or the factory's return."""

    start = js.index(f"    function {name}(")
    ends = [js.find(mark, start + 1) for mark in ("\n    function ", "\n    return Object.freeze")]
    return js[start : min(end for end in ends if end != -1)]


def test_a_view_tab_is_selected_by_one_path_the_click_and_the_key_share() -> None:
    js = _read_app_js()
    # The tab functions are the compositor's (static/view-composition.js); the shell's
    # selectPreviewTab, which the keymap and showPreviewTab call, is its selectTab.
    assert "MetabrowserViewComposition.selectTab(bar, tabId)" in _function_source(
        js, "selectPreviewTab"
    )
    composition = proc_browser.STATIC_DIR.joinpath("view-composition.js").read_text()
    select = composition[
        composition.index("  function selectTab(") : composition.index("  function bindTabs(")
    ]
    assert 'button.setAttribute("aria-selected", on ? "true" : "false")' in select
    assert "setActiveView(host, tabId)" in select
    assert "_metabrowserMount" in select
    assert ".focus(" not in select

    bind = composition[composition.index("  function bindTabs(") :]
    assert "selectTab(bar, button.dataset.tab)" in bind
    show = _function_source(js, "showPreviewTab")
    assert "selectPreviewTab(bar, tabId)" in show
    assert ".click()" not in show


def test_the_view_tab_bar_is_a_tablist_carrying_each_declared_key() -> None:
    render = _function_source(_read_app_js(), "renderFile")
    assert "viewComposition.composition.renderTabs(" in render
    markup = _view_tab_markup()
    assert '<div class="tab-bar" role="tablist">' in markup
    assert 'role="tab" aria-selected="' in markup
    assert "data-view-key=" in markup


def test_a_filter_number_opens_its_menu_through_the_triggers_path() -> None:
    """The trigger's click and the filter numbers share toggleFilterMenu, extracted from the
    filter bar's closure; the keymap's openFilterMenu then focuses the menu's checked row
    through the filter controls' one focus path, which a trigger's own keys and click take
    too (mb-spqw)."""

    js = _read_app_js()
    init = _function_source(js, "initFilterBar")
    assert "onMenuToggle: toggleFilterMenu," in init
    assert "    toggleFilterMenu,\n" in _function_source(js, "shellKeymapShell")
    keymap = proc_browser.STATIC_DIR.joinpath("shell-keymap.js").read_text()
    open_menu = keymap[keymap.index("function openFilterMenu(") :]
    open_menu = open_menu[: open_menu.index("\n    }\n")]
    assert "shell.toggleFilterMenu(key, true)" in open_menu
    assert "filterControls?.focusMenu(bar, key)" in open_menu
    assert ".focus()" not in open_menu
    assert ".click()" not in open_menu
    controls = proc_browser.STATIC_DIR.joinpath("filter-controls.js").read_text()
    focus_menu = controls[controls.index("function focusMenu(") :]
    focus_menu = focus_menu[: focus_menu.index("\n  }\n")]
    assert '.chip-menu-item[aria-checked="true"]' in focus_menu
    assert "row?.focus()" in focus_menu


def test_the_filter_bar_keeps_focus_across_its_rebuild() -> None:
    """Every rebuild of the filter bar holds focus on the control that had it, or on the
    trigger of a menu the rebuild closed, so a pick or a tally refresh never drops focus
    on the page (mb-spqw); the session's stand-in rebuilds the same way."""

    render = _function_source(_read_app_js(), "renderNavFilterBar")
    keep = render.index("var restoreFocus = fc.keepFocus(bar);")
    rebuild = render.index("bar.innerHTML = main + drawer;")
    sync = render.index("shellKeymap?.syncFilters();")
    restore = render.index("restoreFocus();")
    assert keep < rebuild < sync < restore


def test_group_by_rows_declare_the_letters_the_keymap_reads() -> None:
    """Group by's rows declare N, A, and T beside their labels, as the session's stand-in
    renders them; the keymap reads `data-menu-key` from the filter bar and runs each row
    through `filterControls.activateMenuRow`, never a synthesized click (mb-ibo4)."""

    js = _read_app_js()
    options = _function_source(js, "filterGroupOptions")
    assert '{ value: "age", label: "By age", key: "a" }' in options
    assert '{ value: "type", label: "By file type", key: "t" }' in options
    render = _function_source(js, "renderNavFilterBar")
    group = render[render.index('key: "group"') : render.index('menuId: "filter-group-menu"')]
    assert 'anyLabel: "No grouping",' in group
    assert 'anyKey: "n",' in group
    keymap = proc_browser.STATIC_DIR.joinpath("shell-keymap.js").read_text()
    letters = keymap[keymap.index("function syncMenuLetters(") :]
    letters = letters[: letters.index("\n    }\n")]
    assert '".chip-menu-item[data-menu-key]"' in letters
    assert "filterControls?.activateMenuRow(target)" in letters
    assert ".click()" not in letters


def test_the_branch_switcher_handle_is_kept_by_its_module() -> None:
    """The selector's module keeps what it mounted, and the keymap reads it there, so the
    eager app.js keeps no handle: it mounts the selector and reports it."""

    start = _function_source(_read_app_js(), "startSourceRefSelector")
    assert start.index("window.MetabrowserSourceRefSelector?.mount(element);") < start.index(
        "shellKeymap?.syncSource();"
    )
    assert "sourceRefSelector" not in _read_app_js()
    selector = proc_browser.STATIC_DIR.joinpath("source-ref-selector.js").read_text()
    assert "mountedSelector = handle;" in selector
    assert "mounted: () => mountedSelector," in selector
    keymap = proc_browser.STATIC_DIR.joinpath("shell-keymap.js").read_text()
    assert "window.MetabrowserSourceRefSelector?.mounted() ?? null" in keymap


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
    committed = commit.index("shellKeymap?.commitViewTabs(shellKeymap.committedBar());")
    assert replaced < committed < commit.index("finishRetainedPullPage();")
    assert render.count("commitViewTabs") == 1
    assert "shellKeymap" not in render[:commit_start]
    assert "stagedPluginDisposers.push" not in render


def test_a_committed_bar_diffs_its_letters_against_the_ones_held() -> None:
    """``commitViewTabs`` releases nothing itself: ``syncViewTabs`` keeps a letter both bars
    declare under one label, so a move between two files of one kind registers nothing,
    and the ``syncPane()`` after it in the same commit finds every target in place."""

    keymap = proc_browser.STATIC_DIR.joinpath("shell-keymap.js").read_text()
    commit = keymap[keymap.index("function commitViewTabs(") :]
    commit = commit[: commit.index("\n    }\n")]
    assert "releaseViewTab" not in commit
    assert "syncViewTabs(nextBar);" in commit
    assert "syncHeader();" in commit
    sync = keymap[keymap.index("function syncViewTabs(") :]
    sync = sync[: sync.index("\n    }\n")]
    assert "held.target.retarget(button);" in sync


def test_every_main_pane_install_brings_the_keys_along() -> None:
    finish = _function_source(_read_app_js(), "finishRetainedPullPage")
    assert "shellKeymap?.syncPane();" in finish


def test_the_keyboard_infrastructure_owns_the_reveal_and_the_keymap() -> None:
    js = _read_app_js()
    init = _function_source(js, "initKeyboardInfrastructure")
    assert "MetabrowserShellKeymap.createShellKeymap({" in init
    assert "shell: shellKeymapShell()," in init
    assert "MetabrowserKeyReveal.createKeyReveal({" in init
    dispose = _function_source(js, "disposeKeyboardInfrastructure")
    assert dispose.index("keyReveal?.dispose();") < dispose.index("shortcutRegistry?.dispose();")
    assert dispose.index("shellKeymap?.dispose();") < dispose.index("shortcutRegistry?.dispose();")


def test_the_header_parent_is_read_from_the_committed_pane_and_anchors_its_badge() -> None:
    js = _read_app_js()
    keymap = proc_browser.STATIC_DIR.joinpath("shell-keymap.js").read_text()
    parent = keymap[keymap.index("function headerParent()") :]
    parent = parent[: parent.index("\n    }\n")]
    assert '".folder-up[data-nav-dir]:not([disabled])"' in parent
    header = _builder_source(_read_view_header_js(), "viewHeaderHtml")
    assert (
        '`<div class="file-header view-header${parts.className ? ` ${parts.className}` : ""}" data-path="${esc(parts.path)}" data-kbd-badge-anchor>`'
        in header
    )
    filters = _function_source(js, "renderNavFilterBar")
    assert filters.index("bar.innerHTML = main + drawer;") < filters.index(
        "shellKeymap?.syncFilters();"
    )


def test_copying_is_ancillary_and_has_no_key() -> None:
    """Copying a path, a revision, or a hash is ancillary, so no copy control has a key: the
    shell keymap registers no copy command, the commit view lends none, and the SDK keeps
    no keyboard entry to the copy delegate (docs/design-system.md, "Keyboard Shortcuts").
    """

    keymap = proc_browser.STATIC_DIR.joinpath("shell-keymap.js").read_text()
    assert "header.copy" not in keymap
    assert "file-header-copy" not in keymap
    assert "Object.freeze({ createShellKeymap })" in keymap
    panel = proc_browser.STATIC_DIR.joinpath("git-panel.js").read_text()
    assert "attachHeaderCopy" not in panel
    assert "data-kbd-badge-anchor" not in panel
    sdk = proc_browser.STATIC_DIR.joinpath("plugin-sdk.js").read_text()
    assert "copyFromControl" not in sdk
    assert "attachHeaderCopy" not in _read_app_js()


def _tags(source: str, token: str) -> list[str]:
    """Every literal start tag in ``source`` whose class list carries ``token``."""

    return [
        tag
        for tag in re.findall(r"<(?:button|div|span)\b[^<>]*>", source)
        if re.search(rf'class="(?:[^"]*\s)?{re.escape(token)}(?:\s[^"]*)?"', tag)
    ]


def test_the_header_markup_carries_the_hooks_the_keymap_reads() -> None:
    """``headerParent()`` finds Up by class and attribute in markup view-header.js writes,
    and the session renders its own copy of that markup, so these pin the producers: if one
    stops emitting a hook, ``U`` would find nothing and stop working while the session still
    passed."""

    js = _read_view_header_js()
    keymap = proc_browser.STATIC_DIR.joinpath("shell-keymap.js").read_text()

    # Up on a file or a folder: `.folder-up[data-nav-dir]:not([disabled])` in the view
    # header's eyebrow, which both headers build.
    for name in ("renderFolderHeader", "renderFileHeader"):
        render = _builder_source(js, name)
        assert re.search(r"eyebrow:\s+viewHeaderEyebrowHtml\(path\)", render), name
    eyebrow = _builder_source(js, "viewHeaderEyebrowHtml")
    assert eyebrow.index("viewHeaderUpHtml(path)") < eyebrow.index(
        '`<span class="file-header-path folder-breadcrumb">${headerEyebrowAddressHtml(path)}</span>`'
    )
    up = _builder_source(js, "viewHeaderUpHtml")
    assert len(_tags(up, "folder-up")) == 1, up
    # Below the root, Up names its folder and carries the owner mark; at the root it is
    # disabled and names nothing.
    enabled = up[up.index("? `data-tip-text") : up.index("\n        : '")]
    disabled = up[up.index("\n        : '") : up.index(";\n      return")]
    assert 'data-nav-dir="${esc(parent)}"' in enabled
    assert "${ownedControlAttr()}" in enabled
    assert " disabled" in disabled and "data-nav-dir" not in disabled
    assert '".folder-up[data-nav-dir]:not([disabled])"' in keymap

    # The view header anchors the badge beside its Up control.
    header = _builder_source(js, "viewHeaderHtml")
    assert header.index("data-kbd-badge-anchor") < header.index("parts.eyebrow")


def test_the_view_tab_markup_carries_the_hooks_the_keymap_reads() -> None:
    """``committedBar()`` takes the pane's own `.tab-bar` child, and ``declaredTabs()`` reads
    each `.tab-btn[data-view-key]` and its `data-tab`, written by the view compositor."""

    render = _view_tab_markup()
    keymap = proc_browser.STATIC_DIR.joinpath("shell-keymap.js").read_text()
    assert '<div class="tab-bar" role="tablist">' in render
    assert "'<button class=\"tab-btn' +" in render
    assert '\'" type="button" role="tab" aria-selected="\' +' in render
    assert "'\" data-tab=\"' +" in render
    assert (
        'typeof view.key === "string" && view.key ? ` data-view-key="${esc(view.key)}"` : ""'
        in (render)
    )
    assert 'child.classList.contains("tab-bar")' in keymap
    assert 'const VIEW_TAB_SELECTOR = ".tab-btn[data-view-key]";' in keymap
    assert "button.dataset.tab" in keymap


def _shell_html() -> str:
    response = asyncio.run(proc_browser.index(shell_request()))
    return bytes(response.body).decode()


def test_the_keymap_finds_the_pane_and_the_filter_bar_by_the_shells_ids() -> None:
    """The keymap reads the main pane and the filter bar by id, not through app.js, so the
    shell the server renders must carry exactly those ids."""

    keymap = proc_browser.STATIC_DIR.joinpath("shell-keymap.js").read_text()
    assert 'const pane = () => document.getElementById("preview-pane");' in keymap
    assert 'const filterBar = () => document.getElementById("nav-filter-bar");' in keymap
    html = _shell_html()
    assert html.count('id="preview-pane"') == 1
    assert html.count('id="nav-filter-bar"') == 1
    assert "pane: () =>" not in _function_source(_read_app_js(), "shellKeymapShell")
