---
type: is
id: is-01m0jsxesr35r0d8rkrar80nex
title: Goldens for /api/file across every built-in kind
kind: task
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-cli-parity-and-golden-coverage.md
labels: []
dependencies: []
parent_id: is-01m0jsvvcqw7knvxbaq4sn6ddj
created_at: 2026-08-21T18:39:14.743Z
updated_at: 2026-08-30T00:43:34.740Z
closed_at: 2026-08-30T00:43:34.737Z
close_reason: cli-show pins kind and view list for all eight built-in kinds through /api/file; cli-api now pins the content window, its truncation state, and the text_chunk envelope a windowed read returns.
resolution: null
duplicate_of: null
---
Prove the kind each file classifies as and the view list it offers, for all eight built-in kinds: folder, markdown, text, structured, diff, agent-log, unknown-jsonl, binary. This is the registry a reader sees as tabs, and it has no end-to-end coverage today. Include the content window and its truncation state.
