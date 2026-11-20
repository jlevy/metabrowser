---
type: is
id: is-01m7v693rkzpzrha6gkwkybn3s
title: "PR #617 A17: accessibility, find, and print replacements underspecified"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7v68w30f9d3dts3s8ga3rkz
hold: null
hold_until: null
created_at: 2026-11-20T00:39:07.794Z
updated_at: 2026-11-20T00:58:49.719Z
started_at: 2026-11-20T00:39:21.102Z
closed_at: 2026-11-20T00:58:49.719Z
close_reason: 'fixed in `d5ea44d`: Accessibility subsection (a `<table>` with `scope` and `aria-sort` when drawn whole; `role="grid"`, `aria-rowcount` −1 for a lower bound, `aria-rowindex`, `aria-sort` when windowed; cell-level Left/Right so chips and filter values are reachable; hover card on focus; one polite live region); tables under a measured row count drawn whole with native find; search named as the replacement for find only when windowed; the flash uses `--row-flash-bg` and Live Row Arrivals with its reduced-motion treatment; chosen columns live only in the URL, so no persisted state'
resolution: null
duplicate_of: null
---
Severity: Medium. Plan docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md lines 404-430, 440-449. PR #617, review A: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5984058557 (finding A17).
