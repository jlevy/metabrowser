---
type: is
id: is-01m84rpqk0a14rpgjhvqm92ajd
title: "PR #761 A2: the cores walk competes first come with the backfill, so a large catalog's backfill, which Quick Search waits on, takes about an hour"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
created_at: 2026-11-23T17:54:18.334Z
updated_at: 2026-11-23T17:54:18.334Z
---
Review A2 (Medium) of PR #761: https://github.com/jlevy/metabrowser/pull/761#pullrequestreview-6026703603 (review A, senior, round 1, head 3f6e1a0c6).

The backfill reserves nothing (backfill_admitted, pull_list_refresh.py:299-312) and nothing reserves anything for it, while the cores walk, which walks the rows the catalog already holds, runs during the backfill and costs a point for 8 rows where a backfill page costs a point for 100. They take the same first-come points. In the review's model (attic/sim_share.py, production gh_budget and pull_prefetch.reserved), a 5,000-row backfill finishes at 3,613 s; with the walk held until it is done, at 73.5 s, with the walk's progress after 4 h unchanged. At 800 rows both finish at 10.5 s. The plan's new Goal (:47-49, "fills its catalog as fast as GitHub answers its pages") and changelog.d/mb-ztsq.md ("complete as soon as those calls are read") hold only for small catalogs; Quick Search across every state and the ref chooser's pull requests by branch wait on done["all"].

Fix: request_preparation already reads the catalog (pull_cores.py:563): answer held for the background lane while not catalog.done["all"] and backfill_admitted() is true, bounded to a backfill that is running or due so a failing one does not hold the walk for good; or add the backfill's remaining pages to the walk's reserved. Add a test in which a backfill longer than the share's remainder and a walk run together and done["all"] is set before the walk spends. Otherwise narrow the Goal and the fragment.
