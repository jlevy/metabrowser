---
type: is
id: is-01m87bgpe8m20xxs4t7f47qvv8
title: Order checkout revision choices Branches, Remotes, Tags
kind: bug
status: closed
priority: 2
version: 6
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/788
    at: 2026-11-24T18:31:00.522Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45459575260
    at: 2026-11-24T18:31:00.524Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45467510372
    at: 2026-11-24T19:19:26.185Z
delegate: codex@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-24T18:01:32.359Z
updated_at: 2026-11-24T19:19:28.079Z
started_at: 2026-11-24T18:02:07.387Z
closed_at: 2026-11-24T19:19:28.078Z
close_reason: "Merged in #788. Main CI and the real Chrome fixture against the installed Mac runtime passed. The chooser displays Branches, Remotes, Tags and ArrowRight moves from Branches to Remotes."
resolution: null
duplicate_of: null
---
Put Remotes between Branches and Tags in the checkout Files revision chooser. Preserve the two-choice mirror layout and make the visual and keyboard orders agree.

## Notes

PR 788 at ea1dfce0da471fbc1d24fba3887ac0edbcbfccee. Branches, Remotes, Tags in checkout order, Branches / Tags on mirrors, and Chrome Right Arrow selects and focuses Remotes. Standard CI 45457952781 and exact full verify 45457953665.
