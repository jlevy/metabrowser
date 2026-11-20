---
type: is
id: is-01m7wy16p4jdamff7t1kgdq3re
title: "Web panes: allow only about:blank and same-site blob: main-frame loads, not every data:/blob:/about: URL"
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m7wysqjj7ps8vx91xva66k54
created_at: 2026-11-20T16:53:28.898Z
updated_at: 2026-11-20T17:30:26.821Z
---
Review A4 on PR 602 (mb-730z): WebViewPolicy.decide allows a main-frame about, blob, or data URL whatever the site (from NavigationPolicy.inWindowSchemes), as GitHubViewPolicy did. With site-neutral panes the stated rule (a main-frame https page on one of the site's domains stays) understates what a pane will show: such a page has a blank location row, and Copy Link and Open in Browser fall back to the page the pane was opened on. Unverified whether WebKit lets a page script navigate its top frame to data:. Fix: for panes, allow about:blank and a blob: whose embedded origin staysInView; cancel data: main-frame loads; state the rule in WebViewPolicy's doc comment and arch-macos-app.md; test it.
