---
type: is
id: is-01m83kesy0bwjqpe4nwf0ykpha
title: A store's small fetch touches the lending checkout's object files (utime), so the checkout is written
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
delegate: claude-code@spud10
labels:
  - review
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
hold: null
hold_until: null
created_at: 2026-11-23T07:03:21.248Z
updated_at: 2026-11-23T08:09:25.057Z
started_at: 2026-11-23T07:13:23.909Z
closed_at: 2026-11-23T08:09:25.055Z
close_reason: "Fixed in ed2b2ae03 on PR #740 (review A dispositions posted)"
resolution: null
duplicate_of: null
---
PR #740 review A, finding A1 (High). A fetch into an overlay store that brings fewer objects than transfer.unpackLimit is written by unpack-objects, whose write freshens (utime) any received object that already exists, including loose objects and packs reached through objects/info/alternates, that is, the checkout's own files. Reproduced at 7b321c2a9: in tests/test_checkout_store.py's folder fixture, fetch the origin's trunk into the checkout by address (objects held, no ref), push one more commit, serve the folder, wait for ready; fingerprint() then differs for three loose objects under the checkout's .git/objects (mtime). Plain Git 2.56.1 shows the same on a pack. Fix: keep every pack a store receives (fetch.unpackLimit=1, passed with each fetch so stores already made get it; _OVERLAY_CONFIG in cache/acquire.py is written only when a store is made), add the reproduction as a test, and correct the never-written claims until then.
