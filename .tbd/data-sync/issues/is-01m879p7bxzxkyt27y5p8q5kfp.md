---
type: is
id: is-01m879p7bxzxkyt27y5p8q5kfp
title: Use a right arrow for in-app navigation menu actions
kind: bug
status: closed
priority: 2
version: 6
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/786
    at: 2026-11-24T18:30:59.871Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45449769481
    at: 2026-11-24T19:12:06.648Z
delegate: codex@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-24T17:29:36.379Z
updated_at: 2026-11-24T19:12:09.415Z
started_at: 2026-11-24T17:30:19.998Z
closed_at: 2026-11-24T19:12:09.412Z
close_reason: "Merged in #786 and verified on the installed Mac development runtime. In-app navigation actions use the shared right arrow for branches, tags, and pull request heads."
resolution: null
duplicate_of: null
---
Use the shared right arrow in View this branch, View this tag, and equivalent direct navigation actions. Audit shared menu surfaces for any remaining chevron used for navigating to a destination. Keep disclosure and external-link icons distinct and document the design rule.

## Notes

Included in PR 786 at dc391a2f6ef6986e51209b16eab4ea3e7e4b6ae7, exact review 6044262407. The shared ref menu uses the right arrow for branch, tag, and PR-head navigation. Other chevrons were audited as disclosures. Design system and existing Chrome coverage updated. Standard CI 45449762455 and full verify 45449769481 running.
