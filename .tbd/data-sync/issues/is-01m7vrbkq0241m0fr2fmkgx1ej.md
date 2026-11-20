---
type: is
id: is-01m7vrbkq0241m0fr2fmkgx1ej
title: Repository store paths use a 64-hex sha256 directory name; make them short and readable
kind: task
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T05:55:04.031Z
updated_at: 2026-11-20T05:55:54.202Z
started_at: 2026-11-20T05:55:54.198Z
---
Owner, 2026-11-20: '~/.cache/metabrowser/repository-stores/589d51b16fd8f1a20aaa68a5893f815052de0db43f00b84b9f79b8c97d18b306/repository.git ... is ridiculously long, why do we need a hash that long? We should reliably figure out the right number of bits for these IDs to avoid collisions, but keep them readable.' Choose an ID with a readable part (host/owner/repo slug) plus a short hash sized by a stated birthday-bound calculation, with collision detection rather than assumption.
