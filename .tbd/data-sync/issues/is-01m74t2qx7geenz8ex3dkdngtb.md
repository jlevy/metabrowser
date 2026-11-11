---
type: is
id: is-01m74t2qx7geenz8ex3dkdngtb
title: "PR #346 A9: give the CLI equivalent of the automatic comparison request in docs/command-line.md"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m74t21pvwps4wh189z73rspr
created_at: 2026-11-11T08:02:38.630Z
updated_at: 2026-11-11T08:21:21.789Z
closed_at: 2026-11-11T08:21:21.788Z
close_reason: "Fixed in 6c1bc550: docs/command-line.md shows metab ~/src/repo --api /api/plugin/github/pull-refresh --data comparison.json with {number, retry: true, comparison: true}; the after: comparison_route claim matches tests/golden/cli-github-checkout.txt."
resolution: null
duplicate_of: null
---
Suggestion. docs/command-line.md:427 should show metab <repo> --api /api/plugin/github/pull-refresh --data <file with {number, retry: true, comparison: true}>. Review: https://github.com/jlevy/metabrowser/pull/346#pullrequestreview-5855482052 (PR #346, review A, round 1).
