---
type: is
id: is-01m898vaj94xqfvfv34m4m7apt
title: "PR #834 A1: {pull, path} and {commit} multiply a step cost past what MAX_REFERENCES measured"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m898v9wsv87ksj602asv16mq
hold: null
hold_until: null
created_at: 2026-11-25T11:53:23.784Z
updated_at: 2026-11-25T12:13:03.942Z
started_at: 2026-11-25T12:13:03.941Z
---
Medium. guided_review.py:97-104 and 985-1030: each distinct pull request a step cites by {pull, path} costs a record read, a possibly cold whole-comparison manifest (shared_pull_manifest), and a diff run; eight {commit} run eight git log processes (about 170 ms median on the stand-in). Fix: measure the worst case and bound it; batch commit lookups into one git log run; answer a {pull, path} without a kept manifest as not loaded. Review: https://github.com/jlevy/metabrowser/pull/834#pullrequestreview-6057087093
