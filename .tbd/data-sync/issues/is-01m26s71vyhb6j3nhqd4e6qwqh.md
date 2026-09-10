---
type: is
id: is-01m26s71vyhb6j3nhqd4e6qwqh
title: Prevent uncommitted Recent snapshots from repainting replacement views
kind: bug
status: closed
priority: 1
version: 2
labels:
  - release-hardening
  - recent
dependencies: []
created_at: 2026-09-10T23:07:31.069Z
updated_at: 2026-09-10T23:12:29.856Z
closed_at: 2026-09-10T23:12:29.852Z
close_reason: Bound retained Recent rows to their committed window/filter identity, block filesystem/catalog/expiry paints while a replacement owns no committed base, preserve same-selection repair paints, and add exact browserless/golden regression coverage; focused pytest, golden, parity, Biome, and both TypeScript gates passed.
resolution: null
duplicate_of: null
---
Final Astra-max review reproduced a race where an event or expiry scheduled after a replacement Recent request starts can paint the previous committed base under the new request identity while the loading view is uncommitted. Associate paints with committed request ownership, preserve same-selection repair behavior, and add exact browserless/golden coverage for post-start events, expiry, and replacement failure.
