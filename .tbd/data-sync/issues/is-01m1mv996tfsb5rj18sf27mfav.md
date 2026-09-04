---
type: is
id: is-01m1mv996tfsb5rj18sf27mfav
title: "PR #101 R5d: scan_bench.py confounds position-in-pass with the build label"
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:21.497Z
updated_at: 2026-09-04T02:07:14.015Z
closed_at: 2026-09-04T02:07:14.014Z
close_reason: Fixed on claude/inventory-engine-perf; make verify green.
resolution: null
duplicate_of: null
---
Interleaving spreads time drift but never alternates within-pass order: builds[0] always runs first, so page cache and CPU ramp stay confounded with the label. No warmup run is discarded while the decision rule reads raw min/max, biasing toward 'overlapping ranges'. The JSON records no build SHA or dirty flag, so the mode whose purpose is comparing builds cannot substantiate which builds it measured.
