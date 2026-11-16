---
type: is
id: is-01m7k2and11b7wk741vmfrq5nc
title: "PR #452 B3: an appended measurement record repeats two sentences"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7hgpct6qpjeqfpyetf79fef
hold: null
hold_until: null
created_at: 2026-11-16T20:56:08.864Z
updated_at: 2026-11-16T21:14:51.231Z
started_at: 2026-11-16T20:56:16.204Z
closed_at: 2026-11-16T21:14:51.230Z
close_reason: "Fixed in ab51b9063 on PR #452: the grouping records no longer repeat two sentences. Disposition: https://github.com/jlevy/metabrowser/pull/452#issuecomment-6929558034"
resolution: null
duplicate_of: null
---
Review B (Low), PR #452, https://github.com/jlevy/metabrowser/pull/452#pullrequestreview-5927467914. explorations/performance-loop/design-rule-measurements.md:236-241 (at ac20c2c) ends the new grouping record with two sentences already at :218-219 and :242-245; the new record was inserted between the older record's last two sentences. Fix: end the new record at '0.86 s against about 0.42 s' and move :242-245 back to follow :219.
