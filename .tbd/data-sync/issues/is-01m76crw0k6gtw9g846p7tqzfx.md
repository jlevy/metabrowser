---
type: is
id: is-01m76crw0k6gtw9g846p7tqzfx
title: "PR #352 C1: A per-server host name does not make a host-only cookie port-bound"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76crm0dt279t9ak9dpq6pc7
hold: null
hold_until: null
created_at: 2026-11-11T22:48:32.530Z
updated_at: 2026-11-11T22:50:35.905Z
started_at: 2026-11-11T22:48:39.464Z
closed_at: 2026-11-11T22:50:35.892Z
close_reason: "fixed in 3669a358: cookie candidate dropped (host-only matching excludes host names, not ports); no client's credential is a cookie; Authorization header token held per origin, added by one shell helper only to same-origin requests with redirect: error, Authorization chosen because Fetch drops it on cross-origin redirects; first-load and event-stream gate named; claim 4 and plan Testing Strategy test same-host other-port and sibling-host requests with a Host-agnostic header listener; Phase 1, Show X, mb-qzny item, Nov 8 addendum agree. Confirmed by pinned flowmark check, public_hygiene, test_docs_discipline (4 passed), link check, and a re-read."
resolution: null
duplicate_of: null
---
High. PR #352 review C (https://github.com/jlevy/metabrowser/pull/352#pullrequestreview-5866303472); follows B1 (mb-kvvj). docs/project/research/research-2026-11-10-native-app-server-topology.md:647 offers distinct loopback host names with host-only cookies as an origin-bound credential, but host-only matching excludes other host names, not other ports (RFC 6265 sections 5.4 and 8.5): a page at root-a.localhost:8411 sends its cookie to root-a.localhost:8412. Fix: drop the cookie candidate; specify the header token's header and redirect handling; test port-only changes in claim 4 and plan Testing Strategy (plan line 344).
