---
type: is
id: is-01m6tv7b3d98gs7rgkg4m5zg2v
title: Restore focus when choosing a PR stack member
kind: task
status: in_progress
priority: 2
version: 3
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6thd591bhgt6vp9v5ve0326
hold: null
hold_until: null
created_at: 2026-11-07T11:10:13.612Z
updated_at: 2026-11-07T11:39:54.664Z
started_at: 2026-11-07T11:10:14.086Z
---
Review of public pull request325 found keyboard focus can remain in the menu when it becomes hidden. Restore focus to a stable visible control/page destination without scrolling, and pin actual keyboard selection in the existing mount session. Evaluate the title-projection cost with evidence; missing titles array feedback is a same-build contract false positive because the server always emits aligned null fallbacks. No compatibility shim.

## Notes

Menu3097cb7b integrated into325layer and cascaded forward. Capturephase closesmenu and restoresfocused visibletrigger before targetnavigation, without scroll/outsidefocussteal; keyboard/native modifierpaths pinned inexistingmountgolden. Requiredtitlesarray feedback rebutted as paired same-build contract. Titleprojection measured offloop bounded; no unproven optimization. Combinedfocusedgate passes; fullgate/newheadCI/publicdispositions pending.
