---
type: is
id: is-01m78fvzd8jj1kh0fpm00zt8zk
title: Declarative log-adapter detection and parsing in the owning worker
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies:
  - type: blocks
    target: is-01m78fvzzpbj5yemnpk3513vyz
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:08.903Z
updated_at: 2026-11-12T21:17:40.734Z
---
Phase 2 (plan: Log Adapters). Manifest [[log_adapter]] with name and a detect predicate (equals, in, prefix, has, all, any) over the first 20 parsed JSON objects, evaluated host-side; plugin detectors run before built-ins on each line, as today; built-in names unclaimable; duplicate names a --doctor error. Reorder the JSONL paths: /api/file and the pin content routes parse then classify today, and charts.py detects then parses; detect from the head first, classify, then parse, in the owning worker for a plugin adapter. Unknown adapter names get the generic JSONL parser instead of the Claude parser (core behavior change, CHANGELOG). Batched parsing, one parser per stream id, for file views and live streams; a replacement worker re-primes stream parsers by replaying to the cursor, as sse.py's _prime_parser_to_cursor does. Measure the wire shape against today's in-process pipeline (about 2.4x the bare parse by an independent measurement): worker-serialized events spliced without decoding; keep raw unless omitting it wins end to end.

## Notes

Body rewritten 2026-11-12 after the Fable 5.2 design review; it supersedes the earlier review notes. The plan's Key Decisions are awaiting the owner.
