---
type: is
id: is-01m4570rnzf9j30sa49a5zw6sy
title: Align golden evidence parsing with Tryscript 0.3.0 strict blocks
kind: bug
status: in_progress
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-10-05T05:01:39.894Z
updated_at: 2026-10-05T05:05:54.399Z
---
Runner upgrade rejects unclosed executable fences, empty command blocks, multiple prompts, and invalid/duplicate exit codes; non-executable fences are opaque. Update the Python parity/golden extractor to refuse malformed transcripts, and compare accepted blocks plus refusals against the installed package oracle. Invalid transcripts must contribute no parity evidence and actionable golden-check failures.
