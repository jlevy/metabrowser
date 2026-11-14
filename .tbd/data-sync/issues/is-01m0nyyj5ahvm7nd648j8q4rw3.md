---
type: is
id: is-01m0nyyj5ahvm7nd648j8q4rw3
title: "H41: columnar index representation to make the tally pass vectorized"
kind: feature
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T00:04:57.129Z
updated_at: 2026-11-14T18:46:14.607Z
---
Load-time hypothesis H41 (plan-2026-08-21-load-time-performance.md, Hypotheses). A columnar index makes the tally pass vectorized rather than a per-entry Python loop, cheap enough to delete the memo, the bound, and the derived-cost heuristic outright. Metric: tally pass duration at 300,000 and 1,000,000 entries. The heavier alternative to H34 (mb-0cmt).
