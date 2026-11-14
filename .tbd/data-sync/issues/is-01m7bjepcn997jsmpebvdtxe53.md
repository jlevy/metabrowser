---
type: is
id: is-01m7bjepcn997jsmpebvdtxe53
title: pull-cores-prepare takes 2.5 to 6.5 s per request
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-11-13T23:04:02.708Z
updated_at: 2026-11-14T00:01:12.277Z
closed_at: 2026-11-14T00:01:12.276Z
close_reason: "Merged in #412: a ready core answer reuses its catalog snapshot (3 opens for any batch, was 19 for 8); median under load 1,250 ms -> 460 ms. Follow-ups: mb-z5kx, mb-89zo, mb-jopy."
resolution: null
duplicate_of: null
---
Seen in a native-app window's server log (2026-11-13, build 3033): `POST /api/plugin/github/pull-cores-prepare` repeatedly took 2.5 to 6.5 s (9 slow requests in 3 minutes), each answering 94 bytes.

Done when: it is known what the route waits on (GitHub calls, the catalog, a lock), whether a reader waits on it, and either it is made fast or it runs off the request path, measured before and after.
