---
type: is
id: is-01m87bgpe8m20xxs4t7f47qvv8
title: Order checkout revision choices Branches, Remotes, Tags
kind: bug
status: in_progress
priority: 2
version: 3
delegate: codex@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-24T18:01:32.359Z
updated_at: 2026-11-24T18:20:00.687Z
started_at: 2026-11-24T18:02:07.387Z
---
Put Remotes between Branches and Tags in the checkout Files revision chooser. Preserve the two-choice mirror layout and make the visual and keyboard orders agree.

## Notes

PR 788 at ea1dfce0da471fbc1d24fba3887ac0edbcbfccee. Branches, Remotes, Tags in checkout order, Branches / Tags on mirrors, and Chrome Right Arrow selects and focuses Remotes. Standard CI 45457952781 and exact full verify 45457953665.
