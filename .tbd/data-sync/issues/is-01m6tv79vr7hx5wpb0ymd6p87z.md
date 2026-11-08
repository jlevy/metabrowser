---
type: is
id: is-01m6tv79vr7hx5wpb0ymd6p87z
title: Address durable PR core review recovery and currentness findings
kind: task
status: closed
priority: 1
version: 5
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6thd4vjfenzzqnxmbehgph4
hold: null
hold_until: null
created_at: 2026-11-07T11:10:12.343Z
updated_at: 2026-11-08T02:41:40.436Z
started_at: 2026-11-07T11:10:12.868Z
closed_at: 2026-11-08T02:41:40.436Z
close_reason: Owning PRs are actually merged in native stack302 at main68534af933f0fcb38a5d81d62691bb42732d58ab, whose complete tree equals reviewed6cf001cdf and retains it in history. All28publishedheads were green with zero unresolved threads. Full gated6cf verification passed4916tests/9expectedskips,385goldens,audits and distribution; exact wheel installed and previews verified. Post-landing main verification and release preparation remain separate in mb-5k2w/mb-4bd2; no release tag or publication.
resolution: null
duplicate_of: null
---
Review of public pull request323 found scoped backend defects: persist generic-provider failure holds, validate complete records before skipping core preparation, settle/retry same-token partial coverage, recheck mutable currentness without an await after worker disk validation, and retire durable failures after success. Coordinate receipt behavior with the prefetch controller. Add focused production/CLI cases, independently review fixes, forward-merge into the owning layer, and rerun final integration/CI. Do not add compatibility layers.

## Notes

Owning PRs are actually merged in native stack302 at main68534af933f0fcb38a5d81d62691bb42732d58ab, whose complete tree equals reviewed6cf001cdf and retains it in history. All28publishedheads were green with zero unresolved threads. Full gated6cf verification passed4916tests/9expectedskips,385goldens,audits and distribution; exact wheel installed and previews verified. Post-landing main verification and release preparation remain separate in mb-5k2w/mb-4bd2; no release tag or publication.

Backend0fd1feb5 integrated into owning323layer and cascaded forward. Independent backend and layout reviews approve. Durable genericfailurehold, validated readablefullrecordskip, complete partialreceipts/retryleases, no-await finalmemoryrevocationcheck afterdiskwork, and newersuccess/failureordering covered. Combined137focusedtests/15goldens/bothTS pass at72200; fullgate/newheadCI/publicdispositions remain pending.
