---
type: is
id: is-01m7d6qxtf1bn98vt8r1pskpnb
title: "exp-079's WebKit half: WKWebView request counts at final main against the control"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-14T14:17:51.183Z
updated_at: 2026-11-15T06:36:18.093Z
---
mb-ep8a's second reading. exp-079 (PR #431) measured every landed hypothesis at final main (c74d0ef3) against the campaign control (09903292) in Chrome only. The WKWebView probe needs a visible window and an unlocked screen with the user present, and the relaunch reading waits on host mode's sticky port (mb-qzny). Judge nothing new: report request counts per reload and relaunch beside exp-079's Chrome numbers.

## Notes

2026-11-14: correction to the description. The probe's own relaunch reading uses one fixed proxy origin (runbook, wkprobe Scenarios; validated 2026-11-13), so it does not wait on mb-qzny. Only the native app's own relaunch needs host mode's sticky port. Lane W of plan-2026-11-14-performance-campaigns.md: batch this with mb-32en's WebKit half, mb-8k5g and H97 in one session with the user present.
