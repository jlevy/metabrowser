---
type: is
id: is-01m8ad40dysc4w5fr47kpaa5dg
title: "Skill: a stack guide needs .lacking empty, and layers step caps at MAX_REFERENCES"
kind: task
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T22:27:17.052Z
updated_at: 2026-11-26T04:13:55.442Z
started_at: 2026-11-26T04:13:55.435Z
---
Found drafting stack 846's guide. (1) The stack route leaves out the files of layers whose heads are not in the top head (.lacking non-empty), while .truncated stays false; SKILL.md's 'all of them unless .truncated' should say wait until .lacking is empty, or a guide gets path_not_changed. (2) The layers step 'cites every layer', but MAX_REFERENCES=8 (guided_review.py) caps it; say how to cite a stack of more than 8 layers. (3) A guide pinned below a newer top layer reads stale: say to pin to the whole stack's pair.
