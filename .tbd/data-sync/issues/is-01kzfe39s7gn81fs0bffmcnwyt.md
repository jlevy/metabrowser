---
type: is
id: is-01kzfe39s7gn81fs0bffmcnwyt
title: "Quick File catalog only sees ~1% of files: SSE scope is root-depth-2"
kind: bug
status: open
priority: 0
version: 2
labels: []
dependencies: []
created_at: 2026-08-08T00:59:18.182Z
updated_at: 2026-08-08T01:11:34.117Z
---
Files that exist are missing from Quick File results. Root cause: the client's only bulk catalog source is the SSE snapshot at scope=root-depth-2 (app.js EventSource), which carries depth 0-2 only — 127 files on this repo. Deeper paths enter the catalog only via folder expansion, Recent, or direct navigation.

DECIDED DESIGN (mb-ci04, user decision 2026-08-06): client-complete over non-gitignored files.

1. Crawl everything; navigation is unchanged. The inventory keeps indexing gitignored trees.
2. New one-shot bulk feed: GET endpoint returning gzipped minimal JSON {revision, complete, files:[{p, e}]} of NON-GITIGNORED files at all-known scope. Measured 56-83 B/file raw; 270 files / 0.01 MB on this repo; ~1-2 MB gzipped at the 100k design center; bounded by the existing 500k inventory cap.
   Do not widen the existing root-depth-2 EventSource: its full FsEntry shape measured 371 B/entry (5.0 MB for 12.5k), and FileStore/tree decoration want that scope as-is.
3. Live deltas: the root-depth-2 SSE filter drops deep FsChange ops, so the catalog needs its own delta path (a catalog-scoped minimal op stream, or piggyback minimal catalog ops on the existing connection). Ops are small; only the full snapshot was ever the problem.
4. Refetch triggers: fs.resync_required, and walker completion when the first fetch returned complete=false.

Client memory at scale: ~50 MB of JS objects at 100k with today's per-file frozen object; parallel arrays only if 500k-scale becomes real. Ranking already yields and cancels; ~1.5-2s worst-case full scan at 100k is acceptable since superseded scans cancel — incremental narrowing (re-filter the previous result set when the query extends) is the later optimization.

Reconcile docs/project/specs/active/plan-2026-07-17-scalable-file-search.md with this decision as part of the change.
