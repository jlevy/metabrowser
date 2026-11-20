---
type: is
id: is-01m7vrv37xz32vhmy3h0zdjamh
title: A Git revision's files get their age from the last commit that changed them, so By age and file ages work on cloud mirrors and pinned revisions
kind: feature
status: in_progress
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T06:03:31.452Z
updated_at: 2026-11-20T07:08:23.836Z
started_at: 2026-11-20T06:04:12.590Z
---
Owner, 2026-11-20: 'on a cloud mirror repo like the one I just opened for metabrowser I don't see any grouping by age. Is this because it's a fresh clone? Is there any way for us to have the ages of the files represent the actual files from the git commits?' and 'closer to what a normal Git repo would be'. Today a Git revision offers no By age, by design (docs/design-system.md Grouping the Files Tree: 'A Git revision has no modification times'). Give each blob at a revision the commit time of the last commit at or before the revision that changed it (as GitHub's file list does), cached per revision and computed incrementally from a parent revision's answer, bounded by measured budgets on large histories, with an honest state for files not yet dated.

## Notes

Stage 1 (data layer) is PR #643 (claude/revision-file-ages): git last-modified (Git 2.53+), per-commit in-memory cache derived from a cached ancestor, background job file_ages.read, mtime on /api/tree nodes, ages state on /api/index/progress, file_ages block on /api/capabilities, doctor git check with the file ages line, CI admitted-git builds 2.56.1. Owner decision: no fallback walk; older Git means no ages plus a hint. Stage 2 not started: By age grouping, Modified within, /api/recent and sorting on a pin (capabilities recency is still false), the page's own refill poll (needs a browserless session + parity row), /api/file mtime, optional one-level reads for very large repos (0.07-0.13 s measured). Open: compare the 2.56.1 SHA-256 in devtools/build_admitted_git.sh (copied from the Homebrew formula) with kernel.org sha256sums.asc.
