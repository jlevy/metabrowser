---
type: is
id: is-01m7v8cvnhxhpd84rsjmtqqrm3
title: "Decide: may Refresh in folder mode fetch from the origin, and where would the fetch land?"
kind: task
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7v8bs62dz0nqmqb9rnhgsdb
created_at: 2026-11-20T01:16:07.729Z
updated_at: 2026-11-22T21:18:00.657Z
---
Owner, 2026-11-19: "if someone does a fetch, we would want the latest branch, and then separately, we could do fetches at different times."

Following refs after the reader's own fetch needs no decision (the folder-mode follow bead). Metabrowser running the fetch itself does, because the rule decided 2026-09-16 and reaffirmed 2026-11-18 is that Metabrowser never fetches into, switches, locks, or writes a checkout's Git directory (arch-open-modes.md, What Is Never Written).

Options:
(a) Never fetch in folder mode. Refresh re-reads refs only.
(b) Fetch into Metabrowser's own store that borrows the checkout's objects, the PR-review lender store, and show the origin's branches as Metabrowser fetched them, apart from the checkout's own origin/* refs. The checkout stays untouched.
(c) Run git fetch in the checkout on an explicit Refresh. This changes the read-only rule.

Recommendation: (a) now; (b) if a folder should show newer origin branches than the reader fetched.

## Notes

2026-11-22 check: still waiting on the owner. The recommendation stands: (a) Refresh re-reads refs only, never fetching into the checkout. mb-0qgm does not depend on this decision.
