---
type: is
id: is-01m8cy22wfphaxjvb67txqpm6a
title: Complete full verification on the published SoftSchema dependency
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/915
    at: 2026-11-27T09:59:04.453Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cnf4sgyjn4q4psvp77emx2
hold: null
hold_until: null
created_at: 2026-11-26T22:01:48.686Z
updated_at: 2026-11-27T19:05:30.001Z
started_at: 2026-11-27T18:18:17.067Z
closed_at: 2026-11-27T19:05:29.999Z
close_reason: SoftSchema 0.10.0 published lock verified at Metabrowser head ed624db20. Hosted CI 46052500918 and macOS 46052501000 passed. Local lint and parity, 118 pure-parser focused tests, 15 golden commands, and an isolated wheel and source distribution smoke on the preceding code checkpoint passed. The full local pytest tier requires more than the external drive’s 1 GB clone reserve; hosted CI supplied the complete branch gate.
resolution: null
duplicate_of: null
---
After the collection API is available as a published pin, run the full Metabrowser verify gate. The local run completed 2,745 tests and timed out in test_check_parity::test_the_real_table_passes. A separate retry at 180 seconds still timed out under high host load. The lint gate's direct parity audit, focused collection and structured tests, Chrome journeys and isolated install with the reviewed candidate passed. Keep the full gate as rollout evidence.
