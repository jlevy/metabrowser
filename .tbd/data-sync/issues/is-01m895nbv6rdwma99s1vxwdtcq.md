---
type: is
id: is-01m895nbv6rdwma99s1vxwdtcq
title: "PR #830 B1: gapAnswer checks an end answer's range before its comparison"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m895natnk2hpvt6ftqmkeejf
hold: null
hold_until: null
created_at: 2026-11-25T10:57:42.756Z
updated_at: 2026-11-25T11:17:50.496Z
started_at: 2026-11-25T10:57:45.259Z
closed_at: 2026-11-25T11:17:50.495Z
close_reason: "Fixed in dd76f4185: gapAnswer compares comparison_id before the end answer's range; session step adds shrunk.py. Reply https://github.com/jlevy/metabrowser/pull/830#issuecomment-7160839053"
resolution: null
duplicate_of: null
---
Low. src/metabrowser/builtin_plugins/diff/diff-view.js:1567-1580: gapAnswer throws a plain error when an end answer starts before max(1, end - count) and only then compares comparison_id, so an answer from a moved ref whose file is shorter than the gap reads as a failure to retry rather than A6's refusal. Fix: compare comparison_id right after the shape check, and add the case to the session's A6 step. Review: https://github.com/jlevy/metabrowser/pull/830#pullrequestreview-6056253438
