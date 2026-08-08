---
type: is
id: is-01kzfe3raykbx7c9ded9fsrmhq
title: "Decide: ship all filenames to the browser vs bounded server search"
kind: task
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-08-08T00:59:33.085Z
updated_at: 2026-08-08T01:11:10.209Z
closed_at: 2026-08-08T01:11:10.208Z
close_reason: "Decided by the user 2026-08-06: client-complete. The browser holds every non-gitignored filename up to the 500k inventory cap; no bounded server search for the default path. Measurement that settled it: 98% of this repo's inventory is gitignored (node_modules 7.6k, attic 4.4k); the non-ignored set is 270 files / 0.01 MB minimal JSON. Default use case is a few thousand to 100k non-ignored files — 1-2 MB gzipped transfer, tens of MB of browser memory. The plan text 'do not transfer the full inventory' was sized against the unfiltered inventory and is superseded."
---
The Quick File plan and bead mb-3arq state the opposite of the current direction: 'Do not transfer the full inventory', with completeness delivered by a bounded /api/search/files provider instead.

The current instruction is that the browser should hold filenames for every loaded file up to the 500,000 cap, incomplete while indexing and complete afterwards.

These are both viable and they are not the same system:
- client-complete: one bulk minimal path feed (path + logical_ext), zero per-keystroke requests, instant local ranking, cost is transfer and browser memory (~41 MB raw and roughly 100-150 MB of JS objects at 500k)
- server-bounded: small transfers, no browser memory ceiling, but a request per query, cross-runtime ranking parity, and truncation semantics

Settle which one is the target before building either, and reconcile mb-3arq, mb-wzy6, and the scalable-file-search plan with the decision.
