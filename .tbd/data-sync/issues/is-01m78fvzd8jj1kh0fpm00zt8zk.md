---
type: is
id: is-01m78fvzd8jj1kh0fpm00zt8zk
title: Declarative log-adapter detection and parsing in the owning worker
kind: task
status: open
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
assignee: null
delegate: null
labels: []
dependencies:
  - type: blocks
    target: is-01m78fvzzpbj5yemnpk3513vyz
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-12T18:21:08.903Z
updated_at: 2026-11-26T08:37:20.280Z
started_at: 2026-11-26T08:35:34.376Z
---
Phase 3 (plan: Log Adapters, Key Decision 10). Manifest [[log_adapter]] with name and a detect predicate over a stream's first 20 lines, evaluated host-side: equals, in, prefix, has, type, all, any on a parsed object, dotted keys for a nested value, and line_prefix for a line that is not JSON. The last three are what the built-in detectors need (agents/adapters.py tests types, looks inside message, and reads Gemini's banner). The agents plugin declares its five adapters in this language first, and a test holds each declaration to its old detector over the plugin's fixtures before the detector is deleted, so there is one mechanism. A declared adapter registers its parser with register_log_adapter(name, parser_factory=...); the detector argument goes, in the SDK break that carries this; detect_adapter in a worker asks the host. Order stays as on main: discovery order, built-ins first. Unknown names already get the generic parser on main. Reorder the JSONL paths: detect from the head first, classify, then parse, in the owning worker for a worker plugin's adapter. Batched parsing, one parser per stream id, for file views and live streams; a replacement worker re-primes stream parsers by replaying to the cursor, as sse.py's _prime_parser_to_cursor does. Measure the wire shape paired, in-process and proxied on the same machine and log back to back; the first spike's comparison used a figure from another session under another load.

## Notes

Rewritten 2026-11-26 with the plan's second revision (review against main); supersedes the 2026-11-12 body.
