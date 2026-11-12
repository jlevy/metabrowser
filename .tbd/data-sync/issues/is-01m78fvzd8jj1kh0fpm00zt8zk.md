---
type: is
id: is-01m78fvzd8jj1kh0fpm00zt8zk
title: Declarative log-adapter detection and proxied log parsing
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies:
  - type: blocks
    target: is-01m78fvzzpbj5yemnpk3513vyz
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:08.903Z
updated_at: 2026-11-12T18:21:09.493Z
---
Phase 1 (plan: Log Adapters). Manifest [[log_adapter]] with name and a detect predicate over the first 20 parsed JSON objects (equals, in, prefix, has, all, any), evaluated host-side beside the built-in detectors so classification never waits on a worker; built-in names unclaimable and duplicate names a --doctor error. Parsing in the owning worker through register_log_parser factories, batched, one parser per stream id, for file views and live streams; events returned without raw, each with its line index, the host attaching the source line. Measure batch size and whether splicing the worker's JSON into the response without decoding is worth it (spike: transport and codec cost 2.5-3.5x the parse on 100,000 synthetic lines; omitting raw saved about 30% of transport). A manifest addition, so a PATCH bump under the caret gate.
