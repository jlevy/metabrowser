---
type: is
id: is-01m7h0x9d2v61fdbbg3e94ekx9
title: "PR #455 A2: README says every harness starts builds --no-open alone; wkprobe.mjs starts them --exit-on-eof and measures the uncompressed path"
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
created_at: 2026-11-16T01:52:53.153Z
updated_at: 2026-11-16T02:11:15.510Z
started_at: 2026-11-16T01:53:10.989Z
closed_at: 2026-11-16T02:11:15.509Z
close_reason: "A2 fixed in d5356550a: README names wkprobe.mjs and the WebKit gate as starting builds as the app does; PR timed-round notes updated."
resolution: null
duplicate_of: null
---
Severity: Medium. PR #455 (https://github.com/jlevy/metabrowser/pull/455), review A (https://github.com/jlevy/metabrowser/pull/455#pullrequestreview-5913913966), finding A2. References: explorations/performance-loop/README.md:1491-1495; explorations/performance-loop/wkprobe.mjs:157-168, :375, :921.
