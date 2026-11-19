---
type: is
id: is-01m7td3nq8b0dara7v471jp1rt
title: "Branch chooser: list every branch, most recently committed first (no 100-row cap)"
kind: task
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T17:19:15.166Z
updated_at: 2026-11-19T18:07:42.986Z
started_at: 2026-11-19T17:55:57.990Z
---
Owner, 2026-11-19, verbatim: "the branch selector shows: Showing 100 of 1292 branches; filter to narrow. 1. We should not truncate at such an arbitrarily low number as 1,000. We can show all the branches. 2. We should sort them by recency, with most recently modified branches first"

## Notes

Decisions (2026-11-19, branch claude/branch-chooser-all-recent):
- No cap. /api/source/refs answers every matching ref; limit/total/truncated removed from the route, the selector, goldens, and docs. The only bounds are Git's store-read cap and deadline (GIT_SUBPROCESS_MAX_BYTES 32 MiB, about 300,000 refs; GIT_SUBPROCESS_TIMEOUT_S), which refuse rather than cut short. Owner allowed a 1,000-row fallback only if measurement showed a problem; it did not.
- Order: default branch (mirror) or checked-out branch (checkout) first; then newest first by committed_at, the committer date of the commit each ref names, which the row's age shows; undated last; ties by name (Git byte order). Tags use their commit's date, not the tagger date, so order and the age column agree and a tag made later on an old commit does not jump above newer ones. Applied in _newest_first (cache/resolve.py) for branches, tags, and remotes, mirror and checkout alike; Git's --sort dropped (sorting 10,001 rows in Python: 1.8 ms median).
- Caching: none existed on the refs route (comment said not memoized; browser fetches no-store). Reused the existing Git routes memo (git/route_memo.py GIT_ANSWERS) keyed on ref_state + kind + query + served pin/ref + mirror default branch (_refs_answer_key). Bodies over MAX_ENTRY_BYTES (about 9,000 branches) are served, not kept; a repo with more than MAX_REF_ENTRIES loose refs has no key.
- Browser: drawing every row cost 0.6-0.8 s of main thread at 10,001 rows (content-visibility worse), so the list is a window: rows near the view plus ROWS_OVERSCAN (20) on each side, absolutely placed over a sizer; aria-posinset/setsize on each row; keys move by index (focusRow). Badge border made the first row 2px taller, which left gaps; fixed with margin-block -1px on the badge, held by tests/test_ref_selector_long_list_chrome.py.
- Measurements (M1 Pro, load avg 17-35): server for-each-ref 1,301 loose/packed 56-77/25-29 ms, 10,001 loose/packed 383-478/120-124 ms; JSON 291 KB / 2.2 MB. Chrome open painted: 1,301 = 68 ms; 10,001 packed = 249 ms (route 206); 10,001 loose = 666 ms (route 572). No long task over 50 ms; End/ArrowDown/scroll 30-34 ms to the next frame. Screenshot attic/refs-bench/chooser-1300-newest-first.png in the worktree.
