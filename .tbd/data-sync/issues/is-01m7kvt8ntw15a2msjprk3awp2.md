---
type: is
id: is-01m7kvt8ntw15a2msjprk3awp2
title: "PR #496 review B4: the admitted-git gate removes the serial remedy from test_refresh_signals.py"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kvt6zsgb9m5xpanazw7prr
created_at: 2026-11-17T04:21:34.522Z
updated_at: 2026-11-17T04:23:04.202Z
closed_at: 2026-11-17T04:23:04.202Z
close_reason: "Fixed in 008a68b9: Risks, the Testing Strategy row, and mb-dz35 say a module in ADMITTED_GIT_TESTS (test_refresh_signals.py) is fixed, not marked."
resolution: null
duplicate_of: null
---
plan:152-154, :578-580, :659, :694-698. The module is in ADMITTED_GIT_TESTS, so a race there is fixed, not marked.
