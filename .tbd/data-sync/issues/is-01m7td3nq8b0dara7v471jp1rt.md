---
type: is
id: is-01m7td3nq8b0dara7v471jp1rt
title: "Branch chooser: list every branch, most recently committed first (no 100-row cap)"
kind: task
status: closed
priority: 2
version: 8
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/614
    at: 2026-11-20T17:01:18.105Z
delegate: claude-code@spud10
labels:
  - linear
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T17:19:15.166Z
updated_at: 2026-11-20T18:01:38.862Z
started_at: 2026-11-19T17:55:57.990Z
closed_at: 2026-11-19T19:40:24.345Z
close_reason: "Landed in #614 (ab68526e9): the ref chooser lists every ref, checked-out/default first then newest commit first, windowed rows, memoized below MAX_ENTRY_BYTES/MAX_REF_ENTRIES, listing work off the event loop."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: af7d05ea-d601-43a6-b176-77952c7295fd
    linked_at: 2026-11-20T18:01:38.860Z
---
Owner, 2026-11-19, verbatim: "the branch selector shows: Showing 100 of 1292 branches; filter to narrow. 1. We should not truncate at such an arbitrarily low number as 1,000. We can show all the branches. 2. We should sort them by recency, with most recently modified branches first"

## Notes

Decisions (2026-11-19, branch claude/branch-chooser-all-recent):
- No cap. /api/source/refs answers every matching ref; limit/total/truncated removed from the route, the selector, goldens, and docs. The only bounds are Git's store-read cap and deadline (GIT_SUBPROCESS_MAX_BYTES 32 MiB, about 300,000 refs; GIT_SUBPROCESS_TIMEOUT_S), which refuse rather than cut short. Owner allowed a 1,000-row fallback only if measurement showed a problem; it did not.
- Order: default branch (mirror) or checked-out branch (checkout) first; then newest first by committed_at, the committer date of the commit each ref names, which the row's age shows; undated last; ties by name (Git byte order). Tags use their commit's date, not the tagger date, so order and the age column agree and a tag made later on an old commit does not jump above newer ones. Applied in _newest_first (cache/resolve.py) for branches, tags, and remotes, mirror and checkout alike; Git's --sort dropped (sorting 10,001 rows in Python: 1.8 ms median).
- Caching: none existed on the refs route (comment said not memoized; browser fetches no-store). Reused the existing Git routes memo (git/route_memo.py GIT_ANSWERS) keyed on ref_state + kind + query + served pin/ref + mirror default branch (_refs_answer_key). Bodies over MAX_ENTRY_BYTES (about 9,000 branches) are served, not kept; a repo with more than MAX_REF_ENTRIES loose refs has no key.
- Browser: drawing every row cost 0.6-0.8 s of main thread at 10,001 rows (content-visibility worse), so the list is a window: rows near the view plus ROWS_OVERSCAN (20) on each side, absolutely placed over a sizer; aria-posinset/setsize on each row; keys move by index (focusRow). Badge border made the first row 2px taller, which left gaps; fixed with margin-block -1px on the badge, held by tests/test_ref_selector_long_list_chrome.py.
- Measurements (M1 Pro, load avg 17-35): server for-each-ref 1,301 loose/packed 56-77/25-29 ms, 10,001 loose/packed 383-478/120-124 ms; JSON 291 KB / 2.2 MB. Chrome open painted: 1,301 = 68 ms; 10,001 packed = 249 ms (route 206); 10,001 loose = 666 ms (route 572). No long task over 50 ms; End/ArrowDown/scroll 30-34 ms to the next frame. Screenshot attic/refs-bench/chooser-1300-newest-first.png in the worktree.
- PR #614. Review A (0 High, 1 Medium, 4 Low) folded at c7979a7e3. A1: the checkout listing's memo key now includes HEAD's ref as repo_info reads it (repo_info's 5 s TTL made a switch's listing keep the old checked-out branch). A3: parse/sort and filter/encode run in asyncio.to_thread (route_memo.keep_body). A4: rowWindow takes the roving row. A5: role="list", the served row is revealed on first listing, and overflow-anchor: none. Dispositions comment posted.
