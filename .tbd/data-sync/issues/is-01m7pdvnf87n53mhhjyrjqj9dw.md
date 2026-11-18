---
type: is
id: is-01m7pdvnf87n53mhhjyrjqj9dw
title: "macOS app: the view header's GitHub toggle shows github.com for the current item in the window, with a native toggle back to the Metabrowser view"
kind: feature
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7pac84jxgvafgawtsn1wgn0
created_at: 2026-11-18T04:15:23.623Z
updated_at: 2026-11-18T05:54:24.702Z
---
Owner, 2026-11-18: "In general, pages should open in the Metabrowser view, but you should always be able to switch to the GitHub view, and then it's simply a web view onto that page on github.com." The coordinator reversed the earlier "no in-app GitHub browser" for the macOS app: in the app (WKWebView), switching the view header's GitHub toggle shows github.com for the current item in that window, and the toggle stays reachable to switch back, so it lives in native window chrome or an overlay that survives showing github.com.

Split from mb-zp7y's web toggle (static/github-page.js, PR stacked on #550), which today opens the item's github.com page in a new browser tab and, in the app, hands it to the default browser (NavigationPolicy.decideNewWindow -> openExternally).

To decide: navigate the window's web view to github.com versus a second WKWebView over it; where the native toggle sits (title-bar accessory beside TitleBarMark, or a toolbar item); how the app learns the item's github.com URL (from the page, e.g. a message from github-page.js's pageUrl, or from metab, e.g. #540's ProviderUrlReducer.web_url); NavigationPolicy for github.com inside that view (stay in-view for github.com, external for others); and the version floor if metab changes (MetabRequirement.minimumRelease). Never sign or notarize.

## Notes

2026-11-18, review A on #552, A9: the macOS title bar's trailing Metabrowser mark is a link that opens the project on GitHub (TitleBarMarkLayout.swift, docs/macos-app.md), while the view header's gray Metabrowser mark just under it is the inert current view, beside a GitHub mark that opens the item's page. Decide here, with the native toggle, what the title-bar mark becomes. Also from the review's design note: the toggle's link carries nothing that tells the app's NavigationPolicy it is the toggle rather than any github.com link, and after #539 a github.com link handed to the app resolves to the Metabrowser view, the inverse direction; write that rule down here. docs/project/qa/qa-macos-app-hand-checks.md item 10 checks today's behavior (the default browser opens the item's page).
