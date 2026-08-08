---
type: is
id: is-01kzffvfqtgzzak4559ynzyz0s
title: "fdu benchmark harness: cold/warm x raw-walk/with-stats matrix vs dut and gdu"
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-08T01:29:59.289Z
updated_at: 2026-08-08T07:32:07.359Z
closed_at: 2026-08-08T07:32:07.359Z
close_reason: null
---
From the deviations review: 'fastest with full stats' must be benchmarked like-for-like. bfs/dut discard most metadata while fdu retains a full inventory, so the harness must report cold and warm runs separately AND raw-walk vs with-stats numbers separately, on a shared generated corpus (mirroring flowmark benchmarks/generate_corpus.sh). Also carries the revalidation cost-curve spike (open question: is a parallel stat sweep of 500k unchanged files instant-feeling?).
