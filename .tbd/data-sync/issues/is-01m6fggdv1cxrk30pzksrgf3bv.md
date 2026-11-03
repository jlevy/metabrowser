---
type: is
id: is-01m6fggdv1cxrk30pzksrgf3bv
title: "PR #284 B3: file= is stripped so a name with leading or trailing whitespace cannot hydrate alone"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:18.240Z
updated_at: 2026-11-03T02:31:07.076Z
closed_at: 2026-11-03T02:31:07.075Z
close_reason: "B3 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 5609a0b6: file= is the path exactly; test_a_name_with_a_space_at_either_end_hydrates_alone."
resolution: null
duplicate_of: null
---
Medium. Review B https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745588159. diff/sidekick.py:265. Do not strip file.
