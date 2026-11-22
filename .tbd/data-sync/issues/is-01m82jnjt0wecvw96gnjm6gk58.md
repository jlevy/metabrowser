---
type: is
id: is-01m82jnjt0wecvw96gnjm6gk58
title: Widen the navigation pane's default at wide windows
kind: feature
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m82hy6zdk5e5zzmsan8xhw6q
created_at: 2026-11-22T21:30:20.350Z
updated_at: 2026-11-22T21:30:20.350Z
---
OS-599 part 2b. Widen the navigation pane's default, and its inner padding, at wide windows.

Measured on main 472108123: the pane is 300px at every window width from 1024 to 2560, which is 11.7% of a 2560 window. `--tree-pane-width: 300px` (styles.css:443) is the only default; `min-width: 180px`. `initPaneResize` (app.js ~7523-7557, called at 10289) writes an inline width on drag. **The width is not persisted**, so a reload returns to the default and nothing stored needs reconciling.

Plan:
1. The pane sits in the window, not in the doc container, so a `kpress-doc` container query cannot size it. Size it against the window with `clamp(300px, <n>vw, <max>)` on the token. That is honest here, unlike for the doc pane, because the window is the pane's actual container; note that next to the token. Alternatively, make `.container` a size container and query it. Keep 300px at and below today's common widths.
2. Set `<n>` and `<max>` from measurement: at 1920 and 2560, how many tree rows truncate their names at 300 versus the candidates, using this repository and a deep fixture. Record the numbers beside the constant.
3. Step the pane's inner inset (`--pane-header-padding-x`, 12px, styles.css:748) with the same window steps if screenshots show it cramped.
4. A drag still overrides for the session. Whether to persist the dragged width (a pref cookie, as `readPrefCookie`/`writePrefCookie` do, app.js:479-505) is a separate owner decision, out of scope unless asked.
5. Update the tests that hardcode the 300 default and 180 minimum: tests/dom/shortcut-strip-chrome.mjs:45, files-totals-stable-chrome.mjs:73,341, nav-toolbar-wrap.mjs (179-420 sweep), github-pull-header-chrome.mjs:1668, view-header-chrome.mjs:486-529. These should pin the token's computed value at their window width, not 300.

Evidence: a headless-Chrome check of the pane width at 1280, 1920, and 2560; parity row `navigation.toolbar-wrap` (~358) or a new row; design-system.md wherever the pane's width is described. The macOS app's WebView uses the same stylesheet, so check it at one wide window too.
