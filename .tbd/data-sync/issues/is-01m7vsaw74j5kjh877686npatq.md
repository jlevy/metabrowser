---
type: is
id: is-01m7vsaw74j5kjh877686npatq
title: "Event log views: measure open-to-first-row end to end, and skip the generic JSONL envelope for hook-backed kinds"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-19-structured-event-log.md
labels: []
dependencies: []
parent_id: is-01m7ty57a9b1d4gy8xcrhek4xq
created_at: 2026-11-20T06:12:08.546Z
updated_at: 2026-11-20T06:12:08.546Z
---
From senior review A of #633 (A4, Low). Opening an events-*.jsonl segment fetches the generic JSONL file envelope (/api/file) as well as the plugin's route: for a 1.41 MB segment the envelope is 6.76 MB and takes 0.13 to 0.33 s, where the plugin route takes 83 ms cold. The cost measured in the PR (the table build and each view) is not the one a person waits for.

Do: (1) measure, in headless Chrome, from selecting the file to the first Timeline row painted, for a segment at the bound (event_log_views.MAX_VIEW_BYTES) and one a tenth its size, and record the measurement beside the constant, as AGENTS.md asks of a size limit; (2) if the envelope dominates, let a kind whose views are all backed by a data hook skip the generic JSONL envelope (the kind declares it; core stays consumer-agnostic), keeping Raw JSON, which does need the lines, on demand; (3) pin the result in the Chrome test.

Evidence: the reviewer's probes are in review-527-b attic/review-633/ (envelope.time, envelope.out).
