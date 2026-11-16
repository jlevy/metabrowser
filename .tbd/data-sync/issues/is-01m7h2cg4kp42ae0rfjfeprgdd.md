---
type: is
id: is-01m7h2cg4kp42ae0rfjfeprgdd
title: "Judge retained memory against a budget a round registers (PR #442 A2 follow-up)"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7h2ampfg7a32dp0rx5hpwra
created_at: 2026-11-16T02:18:40.146Z
updated_at: 2026-11-16T02:18:40.146Z
---
PR #442 review A, A2 (https://github.com/jlevy/metabrowser/pull/442#pullrequestreview-5913924421): compare now shows the memory metrics (memory_js_heap_kb, memory_embedder_heap_kb, memory_dom_nodes, memory_worker_heap_kb, memory_listeners, memory_documents) report-only, never judged, and names a missing reading in a note rather than a gap. Judging them needs a budget registered before the round, which H112's protocol (mb-wki1) is to name (plan-2026-08-21-load-time-performance.md:962: retained heap and DOM nodes against a budget set before the round), with the A/A spread of revision 6 (mb-tpol) as its basis. Add a --memory-budget (or protocol field) that compare judges each memory metric against, and judge only those. Waits on H112's protocol.
