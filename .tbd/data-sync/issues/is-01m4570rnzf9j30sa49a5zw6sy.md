---
type: is
id: is-01m4570rnzf9j30sa49a5zw6sy
title: Align golden evidence parsing with Tryscript 0.3.0 strict blocks
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-10-05T05:01:39.894Z
updated_at: 2026-10-05T05:29:24.036Z
closed_at: 2026-10-05T05:29:24.036Z
close_reason: "Fixed in PR268 commit f67606b7. Full make verify passed: 4006 pytest tests, 8 live-test skips, 278 goldens, clean npm/Python audits and distribution checks. All nine GitHub checks passed in run 37267339978; review posted on PR268."
resolution: null
duplicate_of: null
---
Runner upgrade rejects unclosed executable fences, empty command blocks, multiple prompts, and invalid/duplicate exit codes; non-executable fences are opaque. Update the Python parity/golden extractor to refuse malformed transcripts, and compare accepted blocks plus refusals against the installed package oracle. Invalid transcripts must contribute no parity evidence and actionable golden-check failures.
