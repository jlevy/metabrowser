---
type: is
id: is-01m7h0x8y0jw25y8arpxgzdqzb
title: "PR #455 A1: --exit-on-eof now also stops compression for a loopback client, and its help and doc section do not say so"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7h0wnsjyz9enemj0de4q5wg
hold: null
hold_until: null
created_at: 2026-11-16T01:52:52.670Z
updated_at: 2026-11-16T02:11:15.054Z
started_at: 2026-11-16T01:53:10.593Z
closed_at: 2026-11-16T02:11:15.053Z
close_reason: "A1 fixed in a8bbfcc46: --exit-on-eof help, docs/command-line.md and CHANGELOG say it also stops compression for a loopback client; CLI-surface golden regenerated."
resolution: null
duplicate_of: null
---
Severity: Medium. PR #455 (https://github.com/jlevy/metabrowser/pull/455), review A (https://github.com/jlevy/metabrowser/pull/455#pullrequestreview-5913913966), finding A1. References: src/metabrowser/cli/main.py:654-660, :850; docs/command-line.md:117-136.
