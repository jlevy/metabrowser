---
type: is
id: is-01m85d2vx2k4gyna131fqfvz5c
title: "PR #768 A2: doctor and docs say every first clone is refused below the reserve, but only GitHub clones gh can size are"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m85d2hj4x5fmcx1vdke1637w
hold: null
hold_until: null
created_at: 2026-11-23T23:50:27.490Z
updated_at: 2026-11-24T00:16:48.194Z
started_at: 2026-11-23T23:50:49.380Z
closed_at: 2026-11-24T00:16:48.194Z
close_reason: "fixed in d8acc98f: check_first_clone in cache/providers.py refuses every first clone below the reserve before any provider (refuse_below_reserve, cache/free_space.py); wording narrowed to first clones that borrow no checkout. Tests: test_first_clone_free_space.py::test_a_volume_below_the_reserve_refuses_every_first_clone, test_acquire_phases.py::test_a_volume_below_the_reserve_refuses_a_first_clone_from_any_origin"
resolution: null
duplicate_of: null
---
Medium. src/metabrowser/cli/doctor.py:692, docs/command-line.md:558-559, docs/project/specs/active/plan-2026-11-18-cli-dependencies-and-doctor.md:322-324. GithubProvider.check_first_clone returns before the free-space comparison for a non-GitHub source, no gh / signed out / offline, or an unknown size. Fix (a): refuse any first clone in core below the reserve. PR 768, review https://github.com/jlevy/metabrowser/pull/768#pullrequestreview-6031209981
