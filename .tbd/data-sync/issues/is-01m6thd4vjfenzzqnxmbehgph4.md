---
type: is
id: is-01m6thd4vjfenzzqnxmbehgph4
title: Persist lightweight PR cores for instant cached descriptions
kind: bug
status: closed
priority: 1
version: 8
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6th4qn5b1s27zkw8rw3736h
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
child_order_hints:
  - is-01m6tv79vr7hx5wpb0ymd6p87z
hold: null
hold_until: null
created_at: 2026-11-07T08:18:38.065Z
updated_at: 2026-11-08T02:41:40.390Z
started_at: 2026-11-07T08:19:49.388Z
closed_at: 2026-11-08T02:41:40.390Z
close_reason: Owning PRs are actually merged in native stack302 at main68534af933f0fcb38a5d81d62691bb42732d58ab, whose complete tree equals reviewed6cf001cdf and retains it in history. All28publishedheads were green with zero unresolved threads. Full gated6cf verification passed4916tests/9expectedskips,385goldens,audits and distribution; exact wheel installed and previews verified. Post-landing main verification and release preparation remain separate in mb-5k2w/mb-4bd2; no release tag or publication.
resolution: null
duplicate_of: null
---
Prepared PR descriptions currently live only in an eight-row CoreWindow and expire after 60 seconds, so viewport changes and later clicks lose useful metadata. Persist the validated lightweight core projection using the existing catalog or private-cache primitives; preserve repository/reader identity and version/fingerprint boundaries, serve validated cached descriptions immediately while refresh proceeds, and keep full discussion/checks/Git acquisition separate. Provide a batch-completion receipt that permits progressive startup warmup without N per-row reads. Measure cache reuse past 60 seconds and across cohorts/server restarts, and test stale/update/auth/offline/rate-limit cases with focused sessions.

## Notes

Owning PRs are actually merged in native stack302 at main68534af933f0fcb38a5d81d62691bb42732d58ab, whose complete tree equals reviewed6cf001cdf and retains it in history. All28publishedheads were green with zero unresolved threads. Full gated6cf verification passed4916tests/9expectedskips,385goldens,audits and distribution; exact wheel installed and previews verified. Post-landing main verification and release preparation remain separate in mb-5k2w/mb-4bd2; no release tag or publication.

Backend251 is independently reviewed and integrated. A new managed CLI process reused unselected pull request309 from the same cache143.534seconds after core publication, with no full record and zero gh calls. Later batches retained durable cores; complete records took precedence. Identity, stale display, cooldown, receipt, and offline-restart cases pass. Final full gate, publication, and CI are pending.

Final backend251 independentlyreviewed and integrated. Real newmanagedCLIprocess readunselected#309 fromsamecache143.534saftercoreobservation, nofullrecord and0ghcalls. Sixpairedcandidates retained49-264durablecores acrosslaterbatches; cacheposttrialmetadataobservationtimesnot equalwindowthroughput. Fullrecordsupersedescore; selectedfull310existsall12trials. Fullgate/PR/CI pending.
