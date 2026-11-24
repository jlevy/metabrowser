---
type: is
id: is-01m85d2x4e2q2yzfj6estpm108
title: "PR #768 A5: the refusal reads wrong for small repositories and a volume below the reserve"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m85d2hj4x5fmcx1vdke1637w
hold: null
hold_until: null
created_at: 2026-11-23T23:50:28.750Z
updated_at: 2026-11-24T00:16:49.024Z
started_at: 2026-11-23T23:50:50.450Z
closed_at: 2026-11-24T00:16:49.024Z
close_reason: "fixed in d8acc98f: size_text picks GB or MB; below-reserve wording; pinned in test_github_provider.py::test_a_refusal_names_each_size_in_a_unit_that_shows_it and test_first_clone_free_space.py"
resolution: null
duplicate_of: null
---
Low. src/metabrowser/builtin_plugins/github/provider.py:270-275, src/metabrowser/cache/free_space.py:66-69. '12 KB, which can take 0.0 GB ... has 0.4 GB free, of which metab leaves 1.0 GB'. Pick a unit for small sizes and word the below-reserve case. PR 768, review https://github.com/jlevy/metabrowser/pull/768#pullrequestreview-6031209981
