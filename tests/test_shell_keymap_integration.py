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

import asyncio
import re
from typing import Any, cast

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
    """The trigger's click and the filter keys share toggleFilterMenu, extracted from the
    filter bar's closure; the keymap's openFilterMenu then focuses the menu's row."""

    js = _read_app_js()
    init = _function_source(js, "initFilterBar")
    assert "onMenuToggle: toggleFilterMenu," in init
    assert "    toggleFilterMenu,\n" in _function_source(js, "shellKeymapShell")
    keymap = proc_browser.STATIC_DIR.joinpath("shell-keymap.js").read_text()
    open_menu = keymap[keymap.index("function openFilterMenu(") :]
    open_menu = open_menu[: open_menu.index("\n    }\n")]
    assert "shell.toggleFilterMenu(key, true)" in open_menu
    assert '.chip-menu-item[aria-checked="true"]' in open_menu
    assert "row?.focus()" in open_menu
    assert ".click()" not in open_menu


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


def test_header_controls_are_read_from_the_committed_pane_and_anchor_their_badges() -> None:
    js = _read_app_js()
    keymap = proc_browser.STATIC_DIR.joinpath("shell-keymap.js").read_text()
    controls = keymap[keymap.index("function headerControls()") :]
    controls = controls[: controls.index("\n    }\n")]
    assert '".folder-up[data-nav-dir]:not([disabled])"' in controls
    assert '".folder-breadcrumb [data-nav-dir]"' in controls
    assert '".file-header-copy"' in controls
    assert "lentCopy && pane()?.contains(lentCopy)" in controls
    assert '<div class="file-header folder-header" data-kbd-badge-anchor>' in js
    assert '<div class="file-header" data-kbd-badge-anchor>' in js
    filters = _function_source(js, "renderNavFilterBar")
    assert filters.index("bar.innerHTML = main + drawer;") < filters.index(
        "shellKeymap?.syncFilters();"
    )


def test_the_commit_view_lends_its_copy_revision_through_the_keymaps_module() -> None:
    """The Git panel and the shell keymap load in one on-demand bundle, so the lent Copy
    lives in the keymap's module, where a rebuilt keymap finds it, and not in app.js."""

    panel = proc_browser.STATIC_DIR.joinpath("git-panel.js").read_text()
    assert "window.MetabrowserShellKeymap?.attachHeaderCopy(revisionCopy)" in panel
    assert '<div class="git-commit-header" data-kbd-badge-anchor>' in panel
    keymap = proc_browser.STATIC_DIR.joinpath("shell-keymap.js").read_text()
    assert "Object.freeze({ attachHeaderCopy, createShellKeymap })" in keymap
    js = _read_app_js()
    assert "attachHeaderCopy" not in js
    assert "headerCopyBridge" not in js
    bundle = proc_browser.STATIC_DIR.joinpath("..", "server.py").read_text()
    tools = bundle[bundle.index('"shell-tools": [') :]
    assert tools.index('{"src": shell_keymap_url}') < tools.index('{"src": git_panel_url}')


def _tags(source: str, token: str) -> list[str]:
    """Every literal start tag in ``source`` whose class list carries ``token``."""

    return [
        tag
        for tag in re.findall(r"<(?:button|div|span)\b[^<>]*>", source)
        if re.search(rf'class="(?:[^"]*\s)?{re.escape(token)}(?:\s[^"]*)?"', tag)
    ]


def test_the_header_markup_carries_the_hooks_the_keymap_reads() -> None:
    """``headerControls()`` finds Up and Copy by class and attribute in markup app.js writes,
    and the session renders its own copy of that markup, so these pin the producers: if
    one stops emitting a hook, ``U`` or ``Y`` would find nothing and stop working while
    the session still passed."""

    js = _read_app_js()
    keymap = proc_browser.STATIC_DIR.joinpath("shell-keymap.js").read_text()

    # Up on a folder: `.folder-up[data-nav-dir]:not([disabled])` inside `.folder-header`.
    folder = _function_source(js, "renderFolderHeader")
    assert '<div class="file-header folder-header" data-kbd-badge-anchor>' in folder
    assert 'header?.classList.contains("folder-header")' in keymap
    up = _tags(folder, "folder-up")
    assert len(up) == 2, up
    enabled = [tag for tag in up if " disabled" not in tag]
    disabled = [tag for tag in up if " disabled" in tag]
    assert len(enabled) == 1 and len(disabled) == 1, up
    assert 'data-nav-dir="${esc(parent)}"' in enabled[0]
    assert "${ownedControlAttr()}" in enabled[0]
    assert "data-nav-dir" not in disabled[0]
    assert '".folder-up[data-nav-dir]:not([disabled])"' in keymap
    assert (
        '`<span class="file-header-path folder-breadcrumb">${headerAddressHtml(path, false)}</span>`'
        in folder
    )

    # Up on a file: the last `.folder-breadcrumb [data-nav-dir]`, a crumb headerAddressHtml
    # writes for each folder above the file, and for the root.
    address = _function_source(js, "headerAddressHtml")
    assert 'class="folder-crumb folder-crumb-root" data-nav-dir=""' in address
    assert 'var attr = last && isFile ? "data-nav-file" : "data-nav-dir";' in address
    assert '${attr}="${esc(walked)}"${ownedControlAttr()}' in address
    assert '".folder-breadcrumb [data-nav-dir]"' in keymap

    # Copy on a file: `.file-header-copy` in the file header's breadcrumb, an owned copy
    # control the SDK's copyFromControl() accepts.
    render = _function_source(js, "renderFile")
    file_header = render[
        render.index("html = '<div class=\"file-header\" data-kbd-badge-anchor>';") :
    ]
    file_header = file_header[: file_header.index('html += "</div>";')]
    crumbs = file_header.index("'<span class=\"file-header-path folder-breadcrumb\">' +")
    assert file_header.index("headerAddressHtml(data.path, true) +") > crumbs
    copy = _tags(file_header, "file-header-copy")
    assert len(copy) == 1, copy
    assert 'data-mb-copy="text"' in copy[0]
    assert "data-mb-copy-text=" in copy[0]
    assert "${ownedControlAttr()}" in copy[0]
    assert file_header.index("file-header-copy") < file_header.index('"</span>";')
    assert '".file-header-copy"' in keymap
    sdk = proc_browser.STATIC_DIR.joinpath("plugin-sdk.js").read_text()
    copy_from_control = sdk[sdk.index("function copyFromControl(") :]
    copy_from_control = copy_from_control[: copy_from_control.index("\n  }\n")]
    assert "if (!control?.dataset.mbCopy || !isOwnedDelegate(control)) {" in copy_from_control
    assert "_handleCopyClick(control);" in copy_from_control
    assert "window.MetabrowserPluginHost?.copyFromControl(target) ?? false" in keymap


def test_the_view_tab_markup_carries_the_hooks_the_keymap_reads() -> None:
    """``committedBar()`` takes the pane's own `.tab-bar` child, and ``declaredTabs()`` reads
    each `.tab-btn[data-view-key]` and its `data-tab`, all written by renderFile."""

    render = _function_source(_read_app_js(), "renderFile")
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
    class _Request:
        def __init__(self) -> None:
            self.query_params: dict[str, str] = {}
            self.headers: dict[str, str] = {}

    response = asyncio.run(proc_browser.index(cast(Any, _Request())))
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
