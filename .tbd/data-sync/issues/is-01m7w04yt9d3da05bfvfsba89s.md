---
type: is
id: is-01m7w04yt9d3da05bfvfsba89s
title: "PR #649 A7: unknown-jsonl depends on agent-log without declaring it"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7w04vfg21q09dmkkdsmbzwp
hold: null
hold_until: null
created_at: 2026-11-20T08:11:14.632Z
updated_at: 2026-11-20T08:47:34.280Z
started_at: 2026-11-20T08:11:21.946Z
closed_at: 2026-11-20T08:47:34.279Z
close_reason: "fixed in b956c4ad1: unknown-jsonl and event-log require agent-log and use its exports via plugins.load; requirement map test; CI run 44703997703 green at 70f180380153ea5a6531e32e219e4ddf2d427883"
resolution: null
duplicate_of: null
---
Low. builtin_plugins/unknown_jsonl/index.js:18-25; event_log/index.js:36. Review: https://github.com/jlevy/metabrowser/pull/649#pullrequestreview-5989412950
