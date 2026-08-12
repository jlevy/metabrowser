---
type: is
id: is-01kzt7xmvxz3jr94dsvfncd9r3
title: "PR #32 review MB32-R3: enforce diagnostic body cap while streaming"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzt7x3qqb7y2qgpbxhjg3k3x
created_at: 2026-08-12T05:43:00.220Z
updated_at: 2026-08-12T05:56:11.399Z
closed_at: 2026-08-12T05:56:11.398Z
close_reason: "Fixed in c263112: the 64 KB cap is enforced incrementally through request.stream and the regression proves later chunks are not consumed."
---
PR #32 senior review MB32-R3 (Low). src/metabrowser/events_route.py api_pending_tally_diagnostic. Enforce the 64 KB limit while reading request.stream so chunked requests cannot be fully buffered first.
