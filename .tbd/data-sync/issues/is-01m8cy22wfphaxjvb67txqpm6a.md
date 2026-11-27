---
type: is
id: is-01m8cy22wfphaxjvb67txqpm6a
title: Complete full verification on the published SoftSchema dependency
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/915
    at: 2026-11-27T09:59:04.453Z
labels: []
dependencies: []
parent_id: is-01m8cnf4sgyjn4q4psvp77emx2
created_at: 2026-11-26T22:01:48.686Z
updated_at: 2026-11-27T09:59:04.454Z
---
After the collection API is available as a published pin, run the full Metabrowser verify gate. The local run completed 2,745 tests and timed out in test_check_parity::test_the_real_table_passes. A separate retry at 180 seconds still timed out under high host load. The lint gate's direct parity audit, focused collection and structured tests, Chrome journeys and isolated install with the reviewed candidate passed. Keep the full gate as rollout evidence.
