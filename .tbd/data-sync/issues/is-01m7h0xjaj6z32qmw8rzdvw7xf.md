---
type: is
id: is-01m7h0xjaj6z32qmw8rzdvw7xf
title: "PR #455 B10: evidence under startup_script_transfer_kb includes a loopback row measured while the server gzipped every answer"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7h0wnsjyz9enemj0de4q5wg
hold: null
hold_until: null
created_at: 2026-11-16T01:53:02.289Z
updated_at: 2026-11-16T02:11:22.585Z
started_at: 2026-11-16T01:53:18.214Z
closed_at: 2026-11-16T02:11:22.584Z
close_reason: "B10 fixed in bea3f5c25: loopback row marked as measured before H115; ceiling rests on the remote rows."
resolution: null
duplicate_of: null
---
Severity: Low. PR #455 (https://github.com/jlevy/metabrowser/pull/455), review B (https://github.com/jlevy/metabrowser/pull/455#pullrequestreview-5914011305), finding B10. References: explorations/performance-loop/performance-budgets.toml:218, :231-238.
