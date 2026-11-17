---
type: is
id: is-01m7kwd0444r5ec4vwxsmg46j3
title: "PR #496 review C3: tests-red silently depends on the plan job's full-history checkout"
kind: bug
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kwcymkyzy307gn8bvwhx18
created_at: 2026-11-17T04:31:48.356Z
updated_at: 2026-11-17T04:32:09.501Z
closed_at: 2026-11-17T04:32:09.500Z
close_reason: "Fixed in 66170948: the sketch notes fetch-depth: 0 on the plan job, check_ci.py (mb-to1c) holds it, and ci_plan.sh writes the reason for a no: exit 1 predates, any other exit a missing commit with a ::warning::."
resolution: null
duplicate_of: null
---
plan:408-410, :444, :558; mb-to1c. State fetch-depth: 0, have check_ci.py hold it, and report why a no was given instead of swallowing exit 128.
