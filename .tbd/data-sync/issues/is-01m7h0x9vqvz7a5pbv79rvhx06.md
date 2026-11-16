---
type: is
id: is-01m7h0x9vqvz7a5pbv79rvhx06
title: "PR #455 A3: server-time.mjs neither reports nor checks which delivery the start produced"
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
created_at: 2026-11-16T01:52:53.622Z
updated_at: 2026-11-16T02:11:15.991Z
started_at: 2026-11-16T01:53:11.379Z
closed_at: 2026-11-16T02:11:15.990Z
close_reason: "A3 fixed in 08dffe80b (banner from a8bbfcc46): server-time/3 prints delivery asked and got, labels an --exit-on-eof start sent gzip; checks in tests/dom/server-time-behavior.mjs."
resolution: null
duplicate_of: null
---
Severity: Medium. PR #455 (https://github.com/jlevy/metabrowser/pull/455), review A (https://github.com/jlevy/metabrowser/pull/455#pullrequestreview-5913913966), finding A3. References: explorations/performance-loop/server-time.mjs:139-140, :339-354; server-time-sums.mjs:465-489.
