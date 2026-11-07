---
type: is
id: is-01m6sppcghnnagtzr2gs9ev631
title: Clarify PR freshness and name GitHub CLI
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m6sq0zex3pr3hngsdmwfayy6
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-07T00:31:49.264Z
updated_at: 2026-11-07T04:26:49.796Z
started_at: 2026-11-07T00:33:27.710Z
closed_at: 2026-11-07T04:26:49.795Z
close_reason: "PR #313 at f5a04df4 is mergeable with green CI and zero unresolved threads. Freshness identifies GitHub CLI and time, while reader identity remains internal to cache validation. Verified in the installed checkout and managed browser."
resolution: null
duplicate_of: null
---
Show age and the GitHub CLI mechanism in normal browser PR freshness. Drop the account name from successful and in-progress UI status. Keep cache and diagnostic provenance and actionable authentication errors. Cover cold preview, refreshing, settled and stale states in existing browserless tests.
