---
type: is
id: is-01m83kez288a4cxagyj1tyht3h
title: A folder's failed first fetch is retried every idle interval with no backoff and no size bound
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
delegate: claude-code@spud10
labels:
  - review
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
hold: null
hold_until: null
created_at: 2026-11-23T07:03:26.526Z
updated_at: 2026-11-23T08:09:25.537Z
started_at: 2026-11-23T07:13:26.838Z
closed_at: 2026-11-23T08:09:25.536Z
close_reason: "Fixed in ed2b2ae03 on PR #740 (review A dispositions posted)"
resolution: null
duplicate_of: null
---
PR #740 review A, finding A2 (Medium). CheckoutStore._keep_fresh (checkout_store.py) asks for the acquisition again each STORE_IDLE_REFRESH_S while there is no session, whatever the failure, on a timer not measured from the failure. The acquisition has a deadline (GIT_ACQUISITION_TIMEOUT_S) and no size bound, and fetches every branch and tag the checkout lacks. A single-branch checkout of a large repository, or a slow link, can therefore download for the whole deadline, discard it, and start again a few minutes later for as long as the server runs, unasked. An origin that refuses (not_found_or_private) is asked every interval too. Fix: back off per consecutive failure from when it ended, with a cap; decide a bound for an acquisition nobody asked for and record its measurement; keep a reader's own Refresh immediate.
