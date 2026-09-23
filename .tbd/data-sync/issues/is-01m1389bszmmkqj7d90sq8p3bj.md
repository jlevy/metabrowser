---
type: is
id: is-01m1389bszmmkqj7d90sq8p3bj
title: Accept local origins as first-class Git sources under the untrusted profile
kind: task
status: in_progress
priority: 1
version: 18
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
delegate: unknown@cursor
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01kzsb4jnyd56wy89xmztkmz2m
  - type: blocks
    target: is-01m2s27ybx4dw3qde29xm6jgqn
  - type: blocks
    target: is-01m2s4vpjy6j5rysn5x8ah2e03
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-08-28T03:58:15.870Z
updated_at: 2026-09-23T00:21:40.866Z
started_at: 2026-09-18T01:15:32.181Z
---
Treat explicit file:// URLs as first-class Git acquisition sources under the untrusted profile. A bare local path is not a Git source: metab /path/to/repo keeps its existing meaning of serving that directory, while acquisition must be requested with file://. The file transport uses Git-aware packing rather than the hardlinked object store created by the implicit --local path form. Do not claim file:// supports blob filtering: verified Git 2.50.1 origins may ignore --filter even with uploadpack.allowFilter; Phase 0 owns that measurement and the full-clone fallback. Acquisition goldens use small deterministic file:// origins and never depend on partial-clone support.

## Notes

File-URL grammar landed in #141 (HEAD ddcce4f9, 7-green) and is now part of the acquire-path phase branch cursor/v011-cache-acquire-path-bd04 @ f369c4cf (with #142–#145). Production classify_root_argument replays url-grammar.json; CLI ROOT stays a string; a bare path is never rewritten to file://. Close when the collapsed layer is reviewed, not when the stack merges to main. gh write failed this session so #141 is still open.

2026-09-20 correction: the last sentence above ("gh write failed this session so #141 is
still open") is false. Verified with gh pr view: #141 is CLOSED (head ddcce4f9), and the
acquire-path branch it fed became #208, also CLOSED, folded into #217. The file-URL
grammar now rides PR #217 https://github.com/jlevy/metabrowser/pull/217 on branch
cursor/v011-cache-acquire-cli-bd04 (head 70091d81, state OPEN).

2026-09-20: removed the edge "mb-k900 blocked by mb-dxmb". It was backwards: this bead's
own close condition is "close when the collapsed layer is reviewed", and mb-k900 is that
review. This bead therefore closes when mb-k900 closes, not before it.
