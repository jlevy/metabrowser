---
type: is
id: is-01m7jeqqdm075zb7jt5dwj57b6
title: "PR #452 A7: render_markdown_summary and --markdown have no test"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpct6qpjeqfpyetf79fef
hold: null
hold_until: null
created_at: 2026-11-16T15:13:45.395Z
updated_at: 2026-11-16T15:27:48.514Z
started_at: 2026-11-16T15:14:16.644Z
closed_at: 2026-11-16T15:27:48.512Z
close_reason: "Fixed in ee8cf8c2d: test_markdown_summary_prints_the_recorded_row and test_markdown_summary_reads_the_figures_a_run_writes; the second fails with a renamed first_count_s (checked by a temporary rename)."
resolution: null
duplicate_of: null
---
Low. devtools/bench_serving.py:1433-1462,:1544-1546. Review A on PR #452: https://github.com/jlevy/metabrowser/pull/452#pullrequestreview-5922214786
