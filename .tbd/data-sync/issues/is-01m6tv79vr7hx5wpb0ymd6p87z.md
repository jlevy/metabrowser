---
type: is
id: is-01m6tv79vr7hx5wpb0ymd6p87z
title: Address durable PR core review recovery and currentness findings
kind: task
status: in_progress
priority: 1
version: 3
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6thd4vjfenzzqnxmbehgph4
hold: null
hold_until: null
created_at: 2026-11-07T11:10:12.343Z
updated_at: 2026-11-07T11:39:54.106Z
started_at: 2026-11-07T11:10:12.868Z
---
Review of public pull request323 found scoped backend defects: persist generic-provider failure holds, validate complete records before skipping core preparation, settle/retry same-token partial coverage, recheck mutable currentness without an await after worker disk validation, and retire durable failures after success. Coordinate receipt behavior with the prefetch controller. Add focused production/CLI cases, independently review fixes, forward-merge into the owning layer, and rerun final integration/CI. Do not add compatibility layers.

## Notes

Backend0fd1feb5 integrated into owning323layer and cascaded forward. Independent backend and layout reviews approve. Durable genericfailurehold, validated readablefullrecordskip, complete partialreceipts/retryleases, no-await finalmemoryrevocationcheck afterdiskwork, and newersuccess/failureordering covered. Combined137focusedtests/15goldens/bothTS pass at72200; fullgate/newheadCI/publicdispositions remain pending.
