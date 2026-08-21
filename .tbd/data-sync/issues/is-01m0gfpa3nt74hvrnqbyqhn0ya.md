---
type: is
id: is-01m0gfpa3nt74hvrnqbyqhn0ya
title: "Aggregate delivery: compute once, push incrementally"
kind: epic
status: open
priority: 1
version: 14
labels: []
dependencies: []
child_order_hints:
  - is-01m0gfq1vyhcv92j37gedat4xs
  - is-01m0gfq29dg0w2b9s716q2x384
  - is-01m0gfq2phqq3c6p85t19xrybr
  - is-01m0hfnfd7vrpcq6d760ntd34c
  - is-01m0hfnftbbthzzmkx6kz7n28n
  - is-01m0hfpfe5c2qqkmxtgnem57rq
  - is-01m0hfpftgcj7dx4sedsd5vgm4
  - is-01m0hk9nqmpp444bh4yyjvxtq7
  - is-01m0hjan4m11x7zxd82a0jbmbq
  - is-01m0hfm55q324z98n722f6ezph
  - is-01m0hfmknkz8znnb2m9gm4x8d4
created_at: 2026-08-20T21:02:05.941Z
updated_at: 2026-08-21T18:31:18.869Z
---
Metabrowser delivers two kinds of inventory state, and only one is done well.

Entries (fs.change over SSE) are computed once, fanned out to every subscriber,
and applied incrementally by client stores (fileStore, directoryTotalsStore,
knownFileCatalog).

Aggregates (/api/rollup, /api/tree) are pull-based: recomputed and re-serialized
per request per client, with no coalescing, no ETag, and a client that replaces
the whole envelope on every refresh.

Measured on a settled 100k-file index, identical concurrent requests for
/api/rollup?path=&depth=3:

  1 concurrent :  30ms
  2            :  57ms
  4            : 107ms
  8            : 236ms

Linear in client count. Eight tabs on one folder means eight full aggregations
and eight serializations of a byte-identical answer.

Goal: bring the aggregate layer up to the model the entry layer already uses --
computed once server-side, delivered without redundant recomputation, and
refined incrementally on the client.

Scope note: SSE currently filters live events to the root-depth-2 scope, which
is why aggregates are pulled at all. Pushing them means either widening that
scope or pushing per-directory aggregate deltas rather than entries.
