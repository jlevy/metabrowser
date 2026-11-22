---
type: is
id: is-01m7zns1bf05k1tz1rpd9ssrkh
title: Prevent the navigation Chrome fixture from accepting a different server on the same port
kind: bug
status: closed
priority: 3
version: 4
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-21T18:26:55.943Z
updated_at: 2026-11-22T20:55:18.053Z
started_at: 2026-11-22T20:42:38.235Z
closed_at: 2026-11-22T20:55:18.050Z
close_reason: "Fixed at the cause by #699 (3b2cfe142): a Serving line now names a port only that server answers on, so the fixture can no longer reach a different server on the same port."
resolution: null
duplicate_of: null
---
In Nightly soak run 44905073328 on main at 98c2dffd, both checkout and history fixture servers announced port 50071. The history server bound it, its generic readiness response was accepted for the checkout server, and the browser later timed out looking for the checkout Markdown link. The other four repeats of that shard passed. Ensure simultaneous fixture servers have distinct ports and readiness validates the expected served folder. Evidence: https://github.com/jlevy/metabrowser/actions/runs/44905073328/job/136848794099

## Notes

2026-11-22: same event as mb-oru2; fixed at the cause in PR #699 (not merged). The server now holds its port as a listening socket from the search on, so two servers started together take different ports and a Serving line names a port only that server answers on. The fixture is unchanged: distinct start ports and a served-folder readiness check are not needed once the port is held. Close with mb-oru2 when #699 merges.
