---
type: is
id: is-01kzfe39s7gn81fs0bffmcnwyt
title: "Quick File catalog only sees ~1% of files: SSE scope is root-depth-2"
kind: bug
status: closed
priority: 0
version: 5
labels: []
dependencies: []
created_at: 2026-08-08T00:59:18.182Z
updated_at: 2026-08-09T18:03:27.814Z
closed_at: 2026-08-09T04:27:33.405Z
close_reason: "Implemented in 16678d3 on feat/quick-file-palette: GET /api/catalog (minimal non-gitignored {p,e}, gzip via middleware, ETag/304, off-loop encode) + catalog.change companions derived at the inventory emit choke point + capability.update on walker completion + client catalog bulk/delta paths with real completeness and memoized snapshot + strict-gate catalog_feed.js (connect-then-fetch, buffer/replay, sentinel/resync refetch). Spec reconciled; mb-3arq stays deferred as the beyond-cap fallback."
---
Files that exist are missing from Quick File results. Root cause: the client catalog is fed only by opportunistic observation, and its only bulk source is the SSE snapshot at scope=root-depth-2 (127 files on this repo vs ~270 non-gitignored).

DECISION CONTEXT: mb-ci04 (user, 2026-08-06) settled client-complete over non-gitignored files. This bead is the delivery mechanism. The earlier recorded mechanism was re-derived from code facts on 2026-08-08 and simplified; measurements and rationale below.

CODE FACTS THAT CHANGED THE DESIGN:
- scope=all-known already exists end-to-end (inventory.entries, snapshot builder, route validation, live-op passthrough). At all-known, snapshot + fs.change ops CONVERGE to the full inventory with no completion event needed.
- The constraint is the wire, not the architecture: FsEntry is ~308 B x 16 fields; the SSE snapshot is one synchronous json.dumps on the event loop (~150 MB at 500k); SSE is NEVER gzipped (Starlette GZipMiddleware excludes text/event-stream). One-shot JSONResponse >= 1 KiB gzips free.
- Every fs.change flows through one choke point: InventoryIndex._emit (inventory.py:887).
- Non-FsChange event types pass the root-depth-2 scope filter UNFILTERED (events_route._filter_event_for_scope) — a new small event type needs zero filter changes.
- gitignored is already a per-entry bool; ext is already the logical compound-tail extension (derive_ext).
- CapabilityUpdate is defined in events.py but has zero producers.

DERIVED DESIGN (supersedes the earlier mechanism in this bead):
1. GET /api/catalog — one-shot JSONResponse {complete, truncated, revision, files:[{p,e}]} of non-gitignored FILES at all-known scope. Encoded off the event loop (asyncio.to_thread); gzip via existing middleware; ETag = status+catalog-revision with 304 support.
2. catalog.change — new tiny event derived in _emit from each FsChange batch: non-gitignored file upserts as {p,e}; removes pass through; upsert with gitignored=true becomes a catalog REMOVE (ignore-flip handling); dir-only batches emit nothing. Rides the EXISTING SSE connection at any scope. No second EventSource, no bespoke delta protocol, one resync path.
3. Correctness without a consistency token: client opens SSE first, buffers catalog.change, fetches /api/catalog, applies bulk, replays buffer. Ops are idempotent by path, so overlap converges. Refetch triggers: the id=0 sentinel fs.snapshot on SSE reconnect, and fs.resync_required. The walker-completion REFETCH trigger from the earlier design is unnecessary — ops converge the data.
4. Completion flag: emit the existing-but-unused CapabilityUpdate on walker completion so the client can flip catalog.complete without polling. (Progress polling remains the fallback.)
5. Client: known_file_catalog gains applyBulkSnapshot (merge, source=catalog-feed), applyCatalogChange, a real complete state (typedef literal false removed), and a revision-memoized snapshot() (today it copies+sorts the whole catalog on every palette status render). New strict-gate static/catalog_feed.js owns the connect-then-fetch/buffer/replay/refetch protocol; app.js wires SSE handlers to it. Observation seams stay for pre-fetch coverage and no-EventSource degradation.
6. Palette/provider status flips to complete wording automatically once snapshot.complete is real.

Scale check at the 100k design center: ~6-8 MB raw minimal JSON, 1-2 MB gzipped, one-time; catalog.change batches are bounded by the existing 256-op fs.change batching. 500k stays the inventory cap and the honest-truncation path.

Reconcile docs/project/specs/active/plan-2026-07-17-scalable-file-search.md as part of the change (its Phase-2 constraint "the browser must not download a complete filename catalog" is superseded by mb-ci04; mb-3arq stays deferred as the beyond-cap fallback).

## Notes

Follow-up: the feed was hardened in 9b6baea after Bugbot review (PR #22) — requestRefetch invalidates in-flight fetches on resync/sentinel, and bulk apply can no longer downgrade completeness (see mb-3tz2 for the full disposition map).
