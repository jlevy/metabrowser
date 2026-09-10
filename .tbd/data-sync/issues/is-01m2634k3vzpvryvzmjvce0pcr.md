---
type: is
id: is-01m2634k3vzpvryvzmjvce0pcr
title: Serialize watcher cancellation and cooperative join
kind: bug
status: closed
priority: 0
version: 2
labels: []
dependencies: []
parent_id: is-01m24nhxxpkrb7cvgyvtxb5d0r
created_at: 2026-09-10T16:41:41.743Z
updated_at: 2026-09-10T17:49:01.034Z
closed_at: 2026-09-10T17:49:01.033Z
close_reason: "Completed in 632f74bc: repeated cancellation now keeps shielding the shared watcher consumer until cooperative finalization. Direct and provider-overlap regressions pass on CPython 3.14t, and the full release gate passed."
resolution: null
duplicate_of: null
---
A resource-budget walker shutdown can race provider close: both cancel the same watcher task. A second cancellation interrupts run_watcher while it shields the Rust-backed consumer cleanup, leaving metabrowser-watchfiles-consumer alive and backend finalization incomplete under CPython 3.14t. Make watcher shutdown cancellation-resistant or share a single stop/join operation, and add the exact concurrent shutdown regression.
