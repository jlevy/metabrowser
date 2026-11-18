---
type: is
id: is-01m7p2ha44m07vhtqayk6gphgj
title: Measure the Overview README's TOC toggle, drawer and deep link in the macOS app's WKWebView (#517 review A9)
kind: task
status: open
priority: 3
version: 1
labels:
  - toc
  - macos
dependencies: []
created_at: 2026-11-18T00:57:29.987Z
updated_at: 2026-11-18T00:57:29.987Z
---
Review A9 on jlevy/metabrowser#517.

Everything #517 and its follow-up measure is headless Chrome. Measure once in the macOS app's WKWebView:
- On a folder's Overview whose README has a table of contents, in a pane under 75 rem: the floating toggle and the drawer sit at the frame's top-right inside the pane, although they are now under a second query container (.folder-overview-host, container-type: inline-size) inside the scroller.
- A deep link to a README heading on the Overview (/view/#section-5): it is delivered once at mount; if File Overview's rollup lands after FIRST_ROLLUP_WAIT_MS (builtin_plugins/folder/file-overview-panel.js) the README moves 143 to 437 px afterwards, which Chrome's scroll anchoring absorbs. Check WebKit keeps the heading at the pane's top.
