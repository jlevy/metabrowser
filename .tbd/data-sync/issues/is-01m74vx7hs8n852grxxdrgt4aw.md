---
type: is
id: is-01m74vx7hs8n852grxxdrgt4aw
title: "PR #347 A3: uncertain merge base is never deepened when the record had to be fitted"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m74vwmegp0f11eb7vj9pnq0t
created_at: 2026-11-11T08:34:35.192Z
updated_at: 2026-11-11T09:41:50.756Z
closed_at: 2026-11-11T09:41:50.755Z
close_reason: "fixed in ecdaaa51: lost writes raise, so the second write expects the written fitted record; test_an_uncertain_base_is_deepened_when_its_record_was_fitted"
resolution: null
duplicate_of: null
---
Severity: Medium. PR #347 review A round 1 at 8dd80d0c (https://github.com/jlevy/metabrowser/pull/347#pullrequestreview-5855504972). References: builtin_plugins/github/pulls.py:795, :848-851.
