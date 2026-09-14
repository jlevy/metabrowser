---
type: is
id: is-01m2f0m23r1xjnjv69c9kses7b
title: "PR #115 review R4: Persistent change below the root during the first recorded row is undetected"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m2f0m0sdxg3fe8v091zxkby8
created_at: 2026-09-14T03:50:52.791Z
updated_at: 2026-09-14T03:50:52.791Z
---
PR #115 review R4 (Low). explorations/performance-loop/run.py:1106-1110, 1189-1191; README.md:189-192; tests/test_performance_loop_gate.py test_record_fingerprints_the_corpus_after_the_measurement.

The launch marker sees only the root level and the full fingerprint is taken after the measurement. A change below the root during the first recorded row that persists gives every row the same post-change fingerprint, so compare accepts them. Harness 21 refused this at record; the new test asserts it records.

Fix (pick one): (a) carry the last recorded fingerprint forward as the next launch's baseline and refuse at record when it differs (no added traversal); (b) narrow the README claim.
