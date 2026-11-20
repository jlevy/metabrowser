---
type: is
id: is-01m7hh0sdnmyfxjrqzgkj1zn9x
title: "PR #466 A11: first-click case unverified in the macOS web view"
kind: bug
status: open
priority: 3
version: 4
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7wys3bp2ndx4v4m26exf0hz
hold: null
hold_until: null
created_at: 2026-11-16T06:34:25.076Z
updated_at: 2026-11-20T17:09:17.814Z
started_at: 2026-11-16T06:34:36.413Z
---
Suggestion. Review A https://github.com/jlevy/metabrowser/pull/466#pullrequestreview-5915498910.

## Notes

Deferred in the PR #466 disposition round at ba5c5f5: the owner's first-click case was not tried in the macOS app's web view. Waiting on a run of the dev app's web view: open Group by, press By file type once on a large folder, and check the trigger reads the choice in that frame and the sections come. Chrome's chosenInFrame and requestsForChoice checks pass at ba5c5f5.
