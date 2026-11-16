---
type: is
id: is-01m7kbr1b46wpcycte58vqjx3y
title: "PR #485 B9: Say how many signing prompts a release brings, and that the lock can lapse during the notarization wait"
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
created_at: 2026-11-16T23:40:44.259Z
updated_at: 2026-11-16T23:48:28.977Z
started_at: 2026-11-16T23:40:44.997Z
closed_at: 2026-11-16T23:48:28.975Z
close_reason: "Fixed in 9e7d362be: O1, Who Can Sign, the local Release Flow and mb-63cx give two signing prompts for a local release and say the 15-minute lock can lapse during the app's notarization wait, so signing and submitting the image ask to unlock again."
resolution: null
duplicate_of: null
---
Suggestion. Two prompts for a local release (build-app.sh:69 signs the app, make-dmg.sh:65 the image); the 15-minute lock can lapse during the app's notarization wait, so signing and submitting the image first ask to unlock. Review B (follow-up, round 2) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5929906549
