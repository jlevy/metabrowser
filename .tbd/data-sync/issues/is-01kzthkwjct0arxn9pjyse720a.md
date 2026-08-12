---
type: is
id: is-01kzthkwjct0arxn9pjyse720a
title: Fix Quick File convergence after reconnect during an incomplete inventory
kind: bug
status: closed
priority: 1
version: 8
labels: []
dependencies: []
parent_id: is-01kzvbhe5e49xmrq7kzjmykfjp
created_at: 2026-08-12T08:32:26.187Z
updated_at: 2026-08-12T16:18:17.575Z
closed_at: 2026-08-12T16:18:17.574Z
close_reason: "PR #34 R1 fixed in ab7284b with full local verification, refreshed green CI and Bugbot, published disposition reply, and resolved inline thread."
---
PR #34 review R1 (medium), src/metabrowser/static/catalog_feed.js:248 and src/metabrowser/static/app.js:5122: a continuity reconnect followed by a file-cap-truncated terminal walk skips onIndexComplete, so the pending authoritative membership refetch never runs and deleted paths may remain searchable. Fix the terminal truncated path without claiming complete root coverage, with a failing DOM regression. Review: https://github.com/jlevy/metabrowser/pull/34#discussion_r3768123248

## Notes

PR #34 review R1 confirmed the capped terminal-state gap. The fix routes every terminal capability update through the catalog feed with its truncated flag, requests an authoritative membership repair after reconnect even when the walk stops at the file cap, and keeps capped root coverage incomplete. Continuity boundaries now downgrade coverage without discarding membership; 304 revalidation restores prior full coverage only when the cached authoritative payload was uncapped. Regressions cover capped repair, coverage downgrade, capped terminal status, and complete/truncated 304 behavior. Full make verify passed on 2026-08-12 with 915 pytest cases and 30 golden scenarios.
