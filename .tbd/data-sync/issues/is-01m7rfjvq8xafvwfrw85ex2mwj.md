---
type: is
id: is-01m7rfjvq8xafvwfrw85ex2mwj
title: "View on GitHub: one split button, upper right, on every page with a github.com counterpart"
kind: feature
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-18T23:24:01.127Z
updated_at: 2026-11-18T23:25:43.037Z
started_at: 2026-11-18T23:25:43.020Z
---
Owner, 2026-11-18, verbatim: "For now, let's simplify the design for the MB|GitHub toggle we had discussed with just a consistent \"[github icon] View on GitHub\" button for all pages that have an equivalent github page (files, folders, PRs, Commits). This should appear consistently in the upper right. By default, it should open a native Swift popover. But it should also have a drop-down menu that lets you either copy the corresponding URL or open it in an external browser. This component should appear consistently everywhere, so we should remove the \"View on GitHub\" link on the PR page that is buried in the metadata and use this View on GitHub button." And: "Let's map that out carefully to the appropriate pages and make sure it's a consistent design system across all pages that have an equivalent and that we could put this in other places in the future too." Supersedes the Metabrowser|GitHub toggle (mb-70d6 web side, mb-lxgw in-window replacement). Web: one reusable component and one page-to-github.com URL mapping (data, CLI/golden parity). App: primary click opens a native NSPopover holding a github.com WKWebView on the shared persistent GitHub data store; menu: Copy Link, Open in Browser.
