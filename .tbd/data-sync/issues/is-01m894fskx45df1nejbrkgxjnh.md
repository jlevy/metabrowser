---
type: is
id: is-01m894fskx45df1nejbrkgxjnh
title: "PR #829 B2: stack retention writes without the source alias lock, and its memo outlives the file"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m894fq5p2chk8wm0qd0vp1yy
hold: null
hold_until: null
created_at: 2026-11-25T10:37:11.674Z
updated_at: 2026-11-25T10:37:16.406Z
started_at: 2026-11-25T10:37:16.405Z
---
Low. PR #829, review B: https://github.com/jlevy/metabrowser/pull/829#pullrequestreview-6055810869. retain_stack_pair replaces stack-<n>.snapshots.json (pull_stack_retained.py:131-138) without source_alias_lock, which clear_pulls relies on (pull_record.py:551, :563). _LAST (pull_stack_retained.py:75, :98-101) keeps reporting a pair as written after cache-clear removed the file, so a page open across a clear loses its drawn comparison at the stack's next move. Fix: write under source_alias_lock; tie the memo to the file's identity (lstat) or clear it from cache_clear_handler.
