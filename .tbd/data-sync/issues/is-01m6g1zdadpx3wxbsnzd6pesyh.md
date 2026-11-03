---
type: is
id: is-01m6g1zdadpx3wxbsnzd6pesyh
title: "PR #284 E3: a cold comparison grows with the pull request, 0.46 s at 1,031 files and 0.95 s at 1,627"
kind: bug
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6g1yw7yj073zja4jqvz0g8b
hold: null
hold_until: null
created_at: 2026-11-03T06:36:35.020Z
updated_at: 2026-11-03T08:05:59.067Z
started_at: 2026-11-03T08:05:59.066Z
---
Medium, from review E of https://github.com/jlevy/metabrowser/pull/284 (https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5747841588), deferred out of that PR.

What review E measured: `builtin_plugins/diff/sidekick.py:384` computes a comparison's manifest on the first request (`diff/adapters/git.py:402-420`, one `--raw --numstat -M50 -C` run), and nothing computes it before a reader asks. Server-Timing on the first request: 419-456 ms at 1,031 files (astral-sh/ruff #29817) in six route-only runs at load 9 to 16, and 446-607 ms in the page runs; 938-971 ms at 1,627 files (astral-sh/ruff #29121), 2 runs at load 2.9 to 5. That alone spends the 500 ms first-line budget past about 1,000 files before the page does anything. A reader who opens Files changed by its address (a link, a reload after a restart, a bookmark) pays it every time a server starts; the Conversation prefetch covers only a reader who lands on Conversation first. The `--raw` half alone is 117 ms on the 1,031-file case (hyperfine), so most of the cost is `--numstat` with `-C`.

Design: compute the manifest at fetch time, beside the record. When `metab` fetches or refreshes a pull request's record into a store (the GitHub plugin's record refresh, `pulls.py`), it already knows the base and head commits. After the fetch lands, run the same manifest computation the route runs (`GitDiffSource.manifest` for the merge-base comparison of the PR's base and head, the same options: `-M50 -C`, the same `MAX_MANIFEST_FILES` bound, the store's read policy with `GIT_ATTR_SOURCE` naming its empty tree) and persist its result in the store's cache directory, keyed exactly as the in-memory `ComparisonCache` keys a manifest: the store's token, both full commit IDs, and the policy, so a different store, an `info/attributes` edit, or a moved head never finds it. The route then reads the persisted manifest on a cold start instead of computing it, and falls back to computing it when the file is absent or its key does not match. Bound the persisted manifests per store (the same 16-comparison policy or by bytes) and write them atomically. The page needs no change: the first request becomes the patch of fifty files (tens of ms) plus reading the manifest. The cost moves to the fetch, which a reader already waits for or which runs in the background.

The cheaper alternative review E offers: start `listed()` for the served pull request's comparison when serve mode starts or when the record arrives, on the cache's own shared task, so the first page request finds the manifest computed. It is one bounded task, but it only helps a server that has been up for about a second before the request, and it computes again on every server start.

Waits on: a decision on persisting manifests in the store's cache (format, invalidation, the cache-directory layout), and the quiet re-run (mb-jwfx) to restate the figures.
