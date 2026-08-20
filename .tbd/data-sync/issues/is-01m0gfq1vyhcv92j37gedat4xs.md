---
type: is
id: is-01m0gfq1vyhcv92j37gedat4xs
title: ETag /api/rollup on the inventory revision so unchanged aggregates cost one 304
kind: task
status: closed
priority: 1
version: 5
labels: []
dependencies:
  - type: blocks
    target: is-01m0gfq29dg0w2b9s716q2x384
parent_id: is-01m0gfpa3nt74hvrnqbyqhn0ya
created_at: 2026-08-20T21:02:30.270Z
updated_at: 2026-08-20T21:10:44.607Z
closed_at: 2026-08-20T21:10:44.606Z
close_reason: "ETag over (build, status, index revision, path, bounds) plus a bounded body cache. Settled 100k index: repeat request 30.8ms -> 7.6ms as a 304; a client without the tag 30.8ms -> 7.1ms from the retained body; 8 staggered clients 236ms -> 32ms. A true simultaneous stampede still scales with client count (35/84/195ms for 1/2/4), which is mb-weoj."
---
/api/rollup carries no ETag, so a client that already holds the current answer
refetches and re-serializes it in full. The catalog and index-progress routes
already use this pattern (build_scoped_etag / matches_if_none_match); the rollup
route does not.

The index already has a monotonic counter that changes on every write
(_rollup_generation), so an ETag over (generation, path, bounded options) is
exact: same token means the response body is unchanged.

Value: a settled index costs one 304 per client per refresh instead of a full
aggregation and serialization. Directly addresses the duplicate-tab case.

Care: the token must cover the response-shaping options (depth, top, ext_top,
ext_rank, filename_top, remaining_top), not just the path, or two clients with
different bounds will share a token and one will get the other's shape.
