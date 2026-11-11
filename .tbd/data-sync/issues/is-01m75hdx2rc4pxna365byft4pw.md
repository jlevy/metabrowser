---
type: is
id: is-01m75hdx2rc4pxna365byft4pw
title: "PR #349 F4: an unchanged block paired with itself raises a false file notice"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m75hdkcm07rrqnt7wf1cqsgg
hold: null
hold_until: null
created_at: 2026-11-11T14:50:41.624Z
updated_at: 2026-11-11T15:29:22.887Z
started_at: 2026-11-11T14:50:49.316Z
closed_at: 2026-11-11T15:29:22.886Z
close_reason: "Fixed in 1d04a797: a pair that renders alike raises the notice only if signatures or non-blank lines differ, and a blank-line-only difference only when nothing visible changed; no corpus file gains a notice from an unchanged block."
resolution: null
duplicate_of: null
---
Review F, F4 (Medium): https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5860564104
