---
type: is
id: is-01m82jn9hd045gp3s3e24bygne
title: A served store with no visible page is fetched every few minutes, so a page opened later is not out of date
kind: feature
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
created_at: 2026-11-22T21:30:10.859Z
updated_at: 2026-11-23T02:31:25.504Z
closed_at: 2026-11-23T02:31:25.501Z
close_reason: "Built in #721 (a3830cf2f)"
resolution: null
duplicate_of: null
---
Owner, 2026-11-22: Metabrowser's own store should be fetched often, since fetching into it is idempotent and safe, and "whenever possible, not out of date". Today no server timer fetches: a mirror refreshes only at startup when stale and when a visible page asks. So a server left running behind a hidden tab or window serves data as old as the last time someone looked.

- Fetch each served store every STORE_IDLE_REFRESH_S (proposed 300 s) while the server runs and no page is visible, as background work that yields to everything a reader waits on (StoreTurn) and takes no network slot from it.
- Same guards as today: the store's fetch lock, follow another process's fetch instead of repeating it, a window after a failure, nothing while offline.
- A branch pin follows what the fetch brings (mb-pq8y), so the page shows it when the reader returns.
- Measure on an idle machine before setting the constant; record it beside the constant. The 2026-11-22 numbers (load average 330): a no-change fetch 1.7 to 5.3 s wall, 0.2 to 0.6 s CPU, 28 to 35 MB.

See the plan's Metabrowser's Own Stores section (Phase 3).
