---
type: is
id: is-01m7kbqtzzz06w5hqa39vmapkz
title: "PR #485 B2: The claim that a hostile tag needs a commit on main is false"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T23:40:37.758Z
updated_at: 2026-11-16T23:48:26.581Z
started_at: 2026-11-16T23:40:38.500Z
closed_at: 2026-11-16T23:48:26.579Z
close_reason: "Fixed in 9e7d362be: both hostile-tag sentences dropped; Who Can Sign, the check job, and Risks say check catches mistakes only since a tag brings its own workflow; the owner confirms the waiting run's commit is RELEASE_COMMIT before approving (Who Can Sign, Release Flow step 3 and sign, O7.2)."
resolution: null
duplicate_of: null
---
Medium. PLAN:326-327, :755-756. The workflow runs from the tagged commit, so a hostile tag brings its own macos-release.yml without the check job. Fix: drop both sentences, say check catches only mistakes, and have the owner confirm the waiting run's commit is RELEASE_COMMIT before approving (O7, Who Can Sign). Review B (follow-up, round 2) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5929906549
