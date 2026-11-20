---
type: is
id: is-01m7vrv37xz32vhmy3h0zdjamh
title: A Git revision's files get their age from the last commit that changed them, so By age and file ages work on cloud mirrors and pinned revisions
kind: feature
status: in_progress
priority: 1
version: 5
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T06:03:31.452Z
updated_at: 2026-11-20T09:14:03.790Z
started_at: 2026-11-20T06:04:12.590Z
---
Owner, 2026-11-20: 'on a cloud mirror repo like the one I just opened for metabrowser I don't see any grouping by age. Is this because it's a fresh clone? Is there any way for us to have the ages of the files represent the actual files from the git commits?' and 'closer to what a normal Git repo would be'. Today a Git revision offers no By age, by design (docs/design-system.md Grouping the Files Tree: 'A Git revision has no modification times'). Give each blob at a revision the commit time of the last commit at or before the revision that changed it (as GitHub's file list does), cached per revision and computed incrementally from a parent revision's answer, bounded by measured budgets on large histories, with an honest state for files not yet dated.

## Notes

Stage 1 (data layer) is PR #643 (claude/revision-file-ages), CI green at head 3cdb69cd5 incl. admitted-git 2.43.7/2.50.1 (absent path) and 2.56.1 (present path). git last-modified (Git 2.53+), per-commit in-memory cache derived from a cached ancestor, background job file_ages.read, mtime on /api/tree nodes, ages state on /api/index/progress (ages=0 opt-out), file_ages block on /api/capabilities, doctor git check with the file ages line (+ app contract changelog entry, Swift DoctorReportTests updated). Owner decision: no fallback walk. Stage 2 (see the update below) covers: By age grouping, Modified within, /api/recent and sorting on a pin (capabilities recency still false), the page's refill poll (needs a browserless session + parity row; pins have no event stream), /api/file mtime, optional one-level reads for very large repos (0.07-0.13 s measured). Resolved: the 2.56.1 SHA-256 matches kernel.org sha256sums.asc.



Update 2026-11-20 (later): senior review A of #643 folded at b94c7f2cb, CI green incl. admitted-git (2.43.7, 2.50.1, 2.56.1), dispositions posted. Changes: a derived read (C ^A) only across a range with no merge (rev-list --merges --count A..C), a budget-cut answer is never a base and is read again after GIT_AGES_CUT_RETRY_AFTER_S, a cancelled read no longer drops a newer one, every step of a read is inside the file_ages.read span, ages.commits dropped, the 45 s budget stated and bounded per read. Stage 1 now says ages show on the next load (no poll). Stage 2 is PR #652 (claude/revision-file-ages-ui, stack #653) with By age, Modified within, /api/recent, /api/file mtime, Undated group, page refill poll (static/revision-ages.js, pin-only startup script, 24 B under the startup budget), re-adds peek and GIT_AGES_POLL_MS, drops RevisionAges.mapping() for a merge walk, and adds GIT_AGES_MAX_CONCURRENT_READS=2 (254 MB resident per read on the 35,824-file history). Open: Git 2.53 to 2.55 untested; lazy per-directory reads for very large repos not built.
