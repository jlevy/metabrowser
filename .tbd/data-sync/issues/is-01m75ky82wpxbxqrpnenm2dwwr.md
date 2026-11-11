---
type: is
id: is-01m75ky82wpxbxqrpnenm2dwwr
title: "PR #348 G5: same_observation lets a failed comparison-only write replace a computed comparison"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m75ky4vdrf0qhqbhy15j46z4
created_at: 2026-11-11T15:34:34.331Z
updated_at: 2026-11-11T15:48:25.297Z
closed_at: 2026-11-11T15:48:25.296Z
close_reason: "Fixed in 0f26f8a9: write_pull_record still refuses a comparison-only writer when the current record has a computed comparison of the same read. Test: test_a_failed_comparison_of_the_same_read_keeps_a_computed_one[fetch_failed, base_uncertain] (fails without the clause)."
resolution: null
duplicate_of: null
---
Review G5 (https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5860828559): pull_record.py:547-552 and :667-685.
