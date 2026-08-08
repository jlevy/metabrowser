---
type: is
id: is-01kzfe3raykbx7c9ded9fsrmhq
title: "Decide: ship all filenames to the browser vs bounded server search"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-08-08T00:59:33.085Z
updated_at: 2026-08-08T00:59:33.085Z
---
The Quick File plan and bead mb-3arq state the opposite of the current direction: 'Do not transfer the full inventory', with completeness delivered by a bounded /api/search/files provider instead.

The current instruction is that the browser should hold filenames for every loaded file up to the 500,000 cap, incomplete while indexing and complete afterwards.

These are both viable and they are not the same system:
- client-complete: one bulk minimal path feed (path + logical_ext), zero per-keystroke requests, instant local ranking, cost is transfer and browser memory (~41 MB raw and roughly 100-150 MB of JS objects at 500k)
- server-bounded: small transfers, no browser memory ceiling, but a request per query, cross-runtime ranking parity, and truncation semantics

Settle which one is the target before building either, and reconcile mb-3arq, mb-wzy6, and the scalable-file-search plan with the decision.
