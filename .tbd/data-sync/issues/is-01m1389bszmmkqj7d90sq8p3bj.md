---
type: is
id: is-01m1389bszmmkqj7d90sq8p3bj
title: Accept local origins as first-class Git sources under the untrusted profile
kind: task
status: in_progress
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
delegate: unknown@cursor
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01kzsb4jnyd56wy89xmztkmz2m
  - type: blocks
    target: is-01m2p1pshr699c6pf8xqeer16j
  - type: blocks
    target: is-01m2s27ybx4dw3qde29xm6jgqn
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-08-28T03:58:15.870Z
updated_at: 2026-09-18T01:34:47.453Z
started_at: 2026-09-18T01:15:32.181Z
---
Treat explicit file:// URLs as first-class Git acquisition sources under the untrusted profile. A bare local path is not a Git source: metab /path/to/repo keeps its existing meaning of serving that directory, while acquisition must be requested with file://. The file transport uses Git-aware packing rather than the hardlinked object store created by the implicit --local path form. Do not claim file:// supports blob filtering: verified Git 2.50.1 origins may ignore --filter even with uploadpack.allowFilter; Phase 0 owns that measurement and the full-clone fallback. Acquisition goldens use small deterministic file:// origins and never depend on partial-clone support.

## Notes

Implemented on cursor/v011-file-url-grammar-bd04, stacked on PR #140. PR https://github.com/jlevy/metabrowser/pull/141 HEAD ddcce4f9: all 7 CI checks green (lint, test 3.12/3.13/3.14/3.14t, distribution, stack-integration). The earlier red on 0df4bccf was the import-boundary regression, fixed by skipping cache.urls on plain local roots. Production classify_root_argument replays url-grammar.json; CLI ROOT stays a string; file:// / https / ssh fail closed until mb-h51g. Close when the layer is reviewed, not when the stack merges to main.
