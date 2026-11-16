---
type: is
id: is-01m7hdtt7vnxqkg3mgneg6wpyz
title: "PR #460 A4: devtools/check_tooltips.py's repeat rule has no test"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjgz0543fxmc38m3p8ajk
hold: null
hold_until: null
created_at: 2026-11-16T05:38:43.578Z
updated_at: 2026-11-16T06:14:51.619Z
started_at: 2026-11-16T05:38:56.127Z
closed_at: 2026-11-16T06:14:51.618Z
close_reason: "fixed in 74113e380 on claude/tooltips-substantive (PR #460 head b6e2e891d); disposition reply https://github.com/jlevy/metabrowser/pull/460#issuecomment-6908929872"
resolution: null
duplicate_of: null
---
Low. devtools/check_tooltips.py:109-112, :161-168, :220-229. Fix: tests/test_check_tooltips.py with the hit and miss table and a clean-tree assertion; widen _REPEAT_H to any attribute order within one object literal, or document the forms it reads. Review A (senior, round 1) on PR #460: https://github.com/jlevy/metabrowser/pull/460#pullrequestreview-5915440680
