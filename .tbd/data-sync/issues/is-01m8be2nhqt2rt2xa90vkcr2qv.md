---
type: is
id: is-01m8be2nhqt2rt2xa90vkcr2qv
title: "Pull request texts: react to metabrowser:pin-changed as rendered diffs do"
kind: task
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
hold: null
hold_until: null
created_at: 2026-11-26T08:03:16.151Z
updated_at: 2026-11-26T10:05:09.422Z
started_at: 2026-11-26T10:05:09.422Z
---
From the Fable review of #874 (L3): /view/ links in a PR's texts localized 'at the head' keep that address after another tab switches the pin, until the pin guard reloads. Re-run enhance on pin change (it is idempotent and reads the authored href).
