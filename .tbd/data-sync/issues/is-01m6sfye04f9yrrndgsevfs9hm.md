---
type: is
id: is-01m6sfye04f9yrrndgsevfs9hm
title: Load older Pulls rows as the reader scrolls
kind: feature
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m6shhkwxasd5rpv91y17qc4w
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-06T22:33:52.899Z
updated_at: 2026-11-06T23:49:12.244Z
started_at: 2026-11-06T22:34:37.794Z
---
Start with the existing 500-row display window. As a reader nears its tail, use the same incremental approach as Git history to append bounded windows from the local PR catalog first, requesting additional metadata through the shared catalog job as needed. Keep selection and scroll stable, respect each filter and its exact total, stop at the real end, and retain an accessible retry or manual load path. Verify a cached and cold catalog with more than 500 rows, keyboard movement, and a filter switch during loading.

## Notes

Added Git-history-style near-tail paging, with 500 initial rows, local-first 100-row automatic pages, retained selection, and explicit Fetch more. Built-in browser with 650 seeded PRs paged 500 to 600 and reached PR #1 without a click. Review and exact full gate in progress.
