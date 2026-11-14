---
type: is
id: is-01m7d6qxtf1bn98vt8r1pskpnb
title: "exp-079's WebKit half: WKWebView request counts at final main against the control"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-14T14:17:51.183Z
updated_at: 2026-11-14T14:17:51.183Z
---
mb-ep8a's second reading. exp-079 (PR #431) measured every landed hypothesis at final main (c74d0ef3) against the campaign control (09903292) in Chrome only. The WKWebView probe needs a visible window and an unlocked screen with the user present, and the relaunch reading waits on host mode's sticky port (mb-qzny). Judge nothing new: report request counts per reload and relaunch beside exp-079's Chrome numbers.
