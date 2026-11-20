---
type: is
id: is-01m7vrv37xz32vhmy3h0zdjamh
title: A Git revision's files get their age from the last commit that changed them, so By age and file ages work on cloud mirrors and pinned revisions
kind: feature
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T06:03:31.452Z
updated_at: 2026-11-20T06:04:12.592Z
started_at: 2026-11-20T06:04:12.590Z
---
Owner, 2026-11-20: 'on a cloud mirror repo like the one I just opened for metabrowser I don't see any grouping by age. Is this because it's a fresh clone? Is there any way for us to have the ages of the files represent the actual files from the git commits?' and 'closer to what a normal Git repo would be'. Today a Git revision offers no By age, by design (docs/design-system.md Grouping the Files Tree: 'A Git revision has no modification times'). Give each blob at a revision the commit time of the last commit at or before the revision that changed it (as GitHub's file list does), cached per revision and computed incrementally from a parent revision's answer, bounded by measured budgets on large histories, with an honest state for files not yet dated.
