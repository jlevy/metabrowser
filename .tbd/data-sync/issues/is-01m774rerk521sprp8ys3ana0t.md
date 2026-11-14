---
type: is
id: is-01m774rerk521sprp8ys3ana0t
title: "Native shell: prewarm at launch, hidden load, reveal on ready, spare web view"
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T05:47:44.786Z
updated_at: 2026-11-14T18:42:13.349Z
---
Native shell half of the research's item 12. apps/macos is on main (#341). A window already loads its page hidden behind a status view and reveals it when the load commits (ShellViews/WebContainerView.swift, ShellCore/Web/PageReveal.swift). What remains: reveal on a ready first view rather than on commit, prewarm a web view at launch, and keep one spare. Revealing on ready needs mb-touu, since a hidden page does not finish its first view. Measured in WKWebView as launch and window-open to ready (the research: 160 ms from prewarm, n=4 pairs; show-to-ready 56-68 ms, n=3).
