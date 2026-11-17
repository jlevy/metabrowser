---
type: is
id: is-01m7kdd8fqzc6mvh76g6xh5m9p
title: "PR #490 A2: an older summary paints over a newer root upsert"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k4tntv9my4ynk41w81g0sj
hold: null
hold_until: null
created_at: 2026-11-17T00:09:48.278Z
updated_at: 2026-11-17T02:33:12.871Z
started_at: 2026-11-17T00:09:56.831Z
closed_at: 2026-11-17T02:33:12.870Z
close_reason: "fixed on PR #490 at 0855877 (CI run 43992596826 green); disposition: https://github.com/jlevy/metabrowser/pull/490#issuecomment-6936212072"
resolution: null
duplicate_of: null
---
Low, PR #490 review A (https://github.com/jlevy/metabrowser/pull/490#pullrequestreview-5929928725). app.js fetchRootSummary and updateRootAggregatePresentation both wrote the line with no ordering, so a tally answered after an upsert stepped the figures back.
