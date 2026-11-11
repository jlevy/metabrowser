---
type: is
id: is-01m73zt8evmhpfk7w862j1rbed
title: Avoid duplicate PR ages and align conversation commit hashes
kind: bug
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m7327d4wd92r1n5bnmr1b0zb
hold: null
hold_until: null
created_at: 2026-11-11T00:23:37.690Z
updated_at: 2026-11-11T00:24:16.535Z
started_at: 2026-11-11T00:23:59.367Z
---
Omit the updated age when it repeats the opened age in PR metadata. Apply the convention to created/updated summaries. Match the monospace commit hash size to the surrounding committed text in PR conversation entries. Show the Rendered | Source chooser only when both formats are available. Document shared design conventions and verify browser behavior.
