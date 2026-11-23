---
type: is
id: is-01m82kqa2v7tyt1xy7kxd0j129
title: "Repository folder: list the origin's branches and tags from Metabrowser's own store beside the checkout, fetched as often as is useful; never fetch into the checkout"
kind: feature
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7v8bs62dz0nqmqb9rnhgsdb
hold: null
hold_until: null
created_at: 2026-11-22T21:48:45.526Z
updated_at: 2026-11-23T13:46:59.986Z
started_at: 2026-11-23T04:51:12.749Z
closed_at: 2026-11-23T13:46:59.985Z
close_reason: "Merged to main in stack #710 (b68cc9571)"
resolution: null
duplicate_of: null
---
Owner, 2026-11-22: Metabrowser's own store should be fetched often, since fetching into it is safe to repeat, and "whenever possible, not out of date"; asked whether folder mode should also show origin branches fetched into that store: "Yes, plan it". This supersedes option (a) of mb-gkq1 for what the folder shows: Refresh in folder mode fetches Metabrowser's store, and still never the checkout.

Design: docs/project/architecture/arch-open-modes.md, Origin Branches in a Repository Folder (not built), and the cadence plan's Metabrowser's Own Stores (Phase 3).

- The store is the overlay that serves a pull request's Changes beside a checkout today, lender = the served checkout (arch-mirror-acquisition-and-refresh.md, The Lending Checkout), holding only objects the checkout lacks. Move its acquisition from the GitHub plugin to core for any repository folder whose origin the lender checks accept, started in the background after the folder's first paint.
- Chooser (GET /api/source/refs): the checkout's own branches from the checkout; the origin's branches and tags from the store, with the last fetch's age; refs only the checkout has (local tags, other remotes) from the checkout. The checkout's own origin/* is not a second list.
- Showing an origin branch serves a revision read from the store (inert) and follows the branch on fetch, as a mirror does (mb-pq8y). This also retires 'a revision is read in place, never through a store that borrows the checkout's objects' from arch-source-sessions-and-pins.md, Not yet.
- Refresh fetches the store and re-reads the checkout's refs. Freshness follows mb-6pzh and mb-l89x.
- Without a store (origin refused, offline, first fetch not done): list the checkout's refs as today and say why.
- Measure the first acquisition on a checkout that is behind its origin (2026-11-11: 21 Git calls on a checkout with no store) and record it.
- Open: mark rows where the reader's own origin/<branch> differs from the origin's.

Update arch-open-modes.md (the mode table's Refresh row, the section, Implementation Status), arch-source-sessions-and-pins.md (Revisions of a Checkout), docs for readers, a changelog.d fragment, and goldens for the chooser listing.
