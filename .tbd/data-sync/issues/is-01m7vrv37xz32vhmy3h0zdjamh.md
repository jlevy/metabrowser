---
type: is
id: is-01m7vrv37xz32vhmy3h0zdjamh
title: A Git revision's files get their age from the last commit that changed them, so By age and file ages work on cloud mirrors and pinned revisions
kind: feature
status: closed
priority: 1
version: 13
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/643
    at: 2026-11-20T17:02:50.712Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/652
    at: 2026-11-20T17:02:50.714Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wys3bp2ndx4v4m26exf0hz
hold: null
hold_until: null
created_at: 2026-11-20T06:03:31.452Z
updated_at: 2026-11-20T19:16:01.673Z
started_at: 2026-11-20T06:04:12.590Z
closed_at: 2026-11-20T11:28:30.865Z
close_reason: "Landed in #643 (commit-derived file ages via git last-modified, doctor git check) and #652 (By age, Modified within, Recent on a revision; redraw when ages land)"
resolution: null
duplicate_of: null
extensions: {}
---
Owner, 2026-11-20: 'on a cloud mirror repo like the one I just opened for metabrowser I don't see any grouping by age. Is this because it's a fresh clone? Is there any way for us to have the ages of the files represent the actual files from the git commits?' and 'closer to what a normal Git repo would be'. Today a Git revision offers no By age, by design (docs/design-system.md Grouping the Files Tree: 'A Git revision has no modification times'). Give each blob at a revision the commit time of the last commit at or before the revision that changed it (as GitHub's file list does), cached per revision and computed incrementally from a parent revision's answer, bounded by measured budgets on large histories, with an honest state for files not yet dated.

## Notes

Stage 1 (data layer) is PR #643 (claude/revision-file-ages), CI green at head 3cdb69cd5 incl. admitted-git 2.43.7/2.50.1 (absent path) and 2.56.1 (present path). git last-modified (Git 2.53+), per-commit in-memory cache derived from a cached ancestor, background job file_ages.read, mtime on /api/tree nodes, ages state on /api/index/progress (ages=0 opt-out), file_ages block on /api/capabilities, doctor git check with the file ages line (+ app contract changelog entry, Swift DoctorReportTests updated). Owner decision: no fallback walk. Stage 2 (see the update below) covers: By age grouping, Modified within, /api/recent and sorting on a pin (capabilities recency still false), the page's refill poll (needs a browserless session + parity row; pins have no event stream), /api/file mtime, optional one-level reads for very large repos (0.07-0.13 s measured). Resolved: the 2.56.1 SHA-256 matches kernel.org sha256sums.asc.



Update 2026-11-20 (later): senior review A of #643 folded at b94c7f2cb, CI green incl. admitted-git (2.43.7, 2.50.1, 2.56.1), dispositions posted. Changes: a derived read (C ^A) only across a range with no merge (rev-list --merges --count A..C), a budget-cut answer is never a base and is read again after GIT_AGES_CUT_RETRY_AFTER_S, a cancelled read no longer drops a newer one, every step of a read is inside the file_ages.read span, ages.commits dropped, the 45 s budget stated and bounded per read. Stage 1 now says ages show on the next load (no poll). Stage 2 is PR #652 (claude/revision-file-ages-ui, stack #653) with By age, Modified within, /api/recent, /api/file mtime, Undated group, page refill poll (static/revision-ages.js, pin-only startup script, 24 B under the startup budget), re-adds peek and GIT_AGES_POLL_MS, drops RevisionAges.mapping() for a merge walk, and adds GIT_AGES_MAX_CONCURRENT_READS=2 (254 MB resident per read on the 35,824-file history). Open: Git 2.53 to 2.55 untested; lazy per-directory reads for very large repos not built.



Update 2026-11-20 (stage 2): #643 merged (f2258ffb0). Senior review A of #652 folded at 2104debfb on claude/revision-file-ages-ui (merged origin/main 8f7f16bb0 first), CI green, dispositions posted on the PR. Changes: a grouped-by-age answer buckets each file once per request (_GitTimes memo) with the ages state read once, tallies summed at C speed (296 ms to 32 ms on 40,000 files), Recent via a heap; the page says what the ages are doing in the filtered-count line and the Undated group's name (a note of its own shifted the tree 19.5 px and was dropped), Modified within counts read an ellipsis while dating, a grouped answer carries recency_tallies; /api/recent counts undated files in any window; /api/file?ages=1 makes --api wait; a cut answer is served while its replacement is read; revision-ages.js is now an on-demand bundle (not a startup script) that retries failed polls, treats a settled response as landing, and takes its give-up from GIT_AGES_WATCH_GIVE_UP_MS; the landing redraws the open file; folder rows in a group are dated by the files that put them there. Filed mb-e3mn: a submodule is in no age group. Note: test_golden_pin_age_groups failed once on CI Python 3.12 (all files Older), passed on rerun and on 3.12 locally; unexplained.
