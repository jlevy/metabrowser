---
type: is
id: is-01m7h2bmrej11b0jakgaws5a19
title: "PR #442 B3: no judged difference is weighed against the recorder's own read-cost difference"
kind: bug
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
hold: null
hold_until: null
created_at: 2026-11-16T02:18:12.109Z
updated_at: 2026-11-20T17:23:42.040Z
started_at: 2026-11-16T02:28:57.156Z
---
Medium finding B3 of review B on PR #442 (round 1, head 33b11020d21d2503ca60237f07b5f32795d3404e): https://github.com/jlevy/metabrowser/pull/442#pullrequestreview-5914046325

References: explorations/performance-loop/transitions-recorder.mjs:91-97, :928-970, :1582-1590; transitions-stats.mjs:157-158, :23-36, :659-674

## Notes

Deferred from PR #442 (coordinator decision). Left: weigh each judged time metric's difference against the difference in median read_cost_to_ready_ms (and for a milestone, milestoneReads[].toMs, which revision 6 now records), marking a result the instrument's own difference could account for, as a note or a gap; or cut the read's DOM-proportional work (mb-gnh9) until a measurement shows the difference is negligible at the largest view. Waits on the A/A run of revision 6 (mb-tpol), which gives the read-cost spread to weigh against.
