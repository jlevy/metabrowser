---
type: is
id: is-01m7kbqyr1865jc7p0c92vapjx
title: "PR #485 B6: Publishing the app draft may make it Latest, and a spent Python version's release is left unexplained"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T23:40:41.600Z
updated_at: 2026-11-16T23:48:28.173Z
started_at: 2026-11-16T23:40:42.332Z
closed_at: 2026-11-16T23:48:28.171Z
close_reason: "Fixed in 9e7d362be: publish with gh release edit macos-vX.Y.Z --draft=false --latest=false (or untick Set as the latest release), checked with gh api .../releases/latest (publishing.md step 5, plan Release Flow step 6 and O7.4, README, mb-xd4o's published run); a spent Python version's notes say it was not published and name the replacement."
resolution: null
duplicate_of: null
---
Low. docs/publishing.md:196-197, :230-233; apps/macos/README.md:498; PLAN:556. Fix: publish with gh release edit --draft=false --latest=false (or untick Latest), have the published check-release.sh run confirm it is not Latest; edit a spent Python version's notes to say it was not published and name the replacement. Review B (follow-up, round 2) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5929906549
