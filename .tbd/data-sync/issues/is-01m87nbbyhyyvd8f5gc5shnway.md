---
type: is
id: is-01m87nbbyhyyvd8f5gc5shnway
title: "Guided review: review E's Lows on #677 (worst-case comment, walk drift test, two overclaims)"
kind: task
status: closed
priority: 3
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/795
    at: 2026-11-24T21:25:19.861Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m87ky2a36j5yg4pf9827xxd6
hold: null
hold_until: null
created_at: 2026-11-24T20:53:23.529Z
updated_at: 2026-11-24T21:25:24.137Z
started_at: 2026-11-24T20:53:45.045Z
closed_at: 2026-11-24T21:25:24.137Z
close_reason: "Addressed in #795 (0c4e8720d): E1 MAX_ITEMS comment names deep flow nesting, re-measured at 2.69 s thread CPU, bound declined with reason; E2 test_the_shape_walk_reaches_every_nested_model; E3 three rewordings."
resolution: null
duplicate_of: null
---
Review E on #677 (pullrequestreview-6047208805): E1 the MAX_ITEMS comment's densest shape is deep flow nesting (62-deep groups ~3.4x D's case), re-measure and optionally bound flow nesting before YAML; E2 the shape walk's nesting is hand-written, add a test that every _Model or list[_Model] field reachable from Collection is walked (or derive it); E3 reword the docstrings that say the walk names softschema's first place, and arch-github-pull-requests.md:983-984 (only undeclared keys are quadratic).
