---
type: is
id: is-01m84jcvbcn1d54ba93avka51z
title: "PR #737 D1: the catalog's part holds a first visit's backfill and cores walk to 8 points an hour, so Quick Search and branch rows stay incomplete for hours"
kind: bug
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-23T16:04:03.050Z
updated_at: 2026-11-23T16:10:25.844Z
started_at: 2026-11-23T16:10:25.841Z
---
Review D1 (Medium) of PR #737, a post-merge follow-up review: https://github.com/jlevy/metabrowser/pull/737#pullrequestreview-6024990059 (review D).

CATALOG_SPECULATIVE_CORE_PER_HOUR (8, gh_budget.py), added by 267e15c30 for review B1, holds the catalog's backfill and its cores walk together to 8 points a rolling hour. Before #737 (its base 08c42f59e) the backfill asked only the floor and a rate hold, and the cores walk asked no governor, so a cold 800-row catalog (8 backfill pages, 100 walk batches) was read in minutes. Now it takes about 13.5 hours; 5,000 rows about 84 hours.

A scratch test (1,300 rows, the reader's Open prefix asked, each page one point): the job reads 8 of 13 backfill pages and stops with done["all"] false; catalog_search("#3") answers complete: false without #3 or 399..396. With the share alone, or with no share, all 13 pages are read and the search is complete.

What waits on the backfill: Quick Search across every state (pull_catalog.py catalog_search's complete; search-controller.js says "No matching cached pull requests." when nothing is refreshing), the ref chooser's pull requests by head branch (ref_pulls.py), and the walk. A reader's Reload does not help (backfill_admitted in its job too). Every CATALOG_PROJECTION upgrade restarts every catalog's backfill.

Why 8: the prefetch's caps are reserved at their worst-case 92 in every hour, whatever it spends; on a warm cache most of that is unspent.

Fix (pick one): take the backfill out of the catalog part (100 rows a point, once per epoch); reserve only what the prefetch can still spend, and only while its lane is asking; or give a cold fill an allowance of its own outside the hourly share. Either way record one real first visit's governor.ceiling beside the constant, say in the changelog fragment what a first visit costs the reader, and pin the order through the production paths (see the D2 bead).

Needs the owner's decision on the design.
