---
type: is
id: is-01m7dm4wcgvhdvnjpcx06pp3wg
title: "Files, Commits and Pulls: one consistent metadata line under the tabs"
kind: bug
status: in_progress
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-14T18:12:07.183Z
updated_at: 2026-11-14T18:12:08.080Z
---
The user (2026-11-14): "under the files, commits, and pulls tabs, there is metadata below giving tallies of totals, when it was fetched, and so on. This small metadata section should always appear with the same amount of padding and styling on the text. It currently is inconsistent."

The rows: the Files tab's tree summary (file and ignored counts, sizes), the Commits tab's line (commit count, begun, fetched or refreshed), and the Pulls tab's line (PR count on the repository, updated or fetched). Done when the three share one component or class with one padding, font size, weight, color and spacing between items, measured in Chrome and WebKit across the tabs, documented in docs/design-system.md, and pinned by a test.
