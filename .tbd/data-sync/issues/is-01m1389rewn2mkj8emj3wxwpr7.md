---
type: is
id: is-01m1389rewn2mkj8emj3wxwpr7
title: "Cache goldens: layout, acquisition, crash recovery, and URL grammar"
kind: task
status: in_progress
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
delegate: codex@spud10
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2kwk6h6pzxanejy6c339r08
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-08-28T03:58:28.818Z
updated_at: 2026-09-16T21:24:53.016Z
started_at: 2026-09-16T21:10:44.821Z
---
Golden sessions prove the cache end to end with no browser or network: owner-only f01 source/store layout and future-format refusal; acquisition from a deterministic file:// origin into one worktree-free store; a second offline open reusing the same full-OID subject; interrupted publication and startup reclamation; URL grammar; and two concurrent revision subjects without checkout, index, branch switching, or worktree directories. Hermeticity uses isolated METABROWSER_HOME and null global/system Git configs. Assert real deterministic OIDs and logical state, never pack filenames.

## Notes

Normalizer rules arrive with these goldens (PR #116 review R1): add the <HOME> rule to src/metabrowser/normalize.py with cli-cache-layout (Cache 1A), and the opt-in <MTIME> rule for mtime/mtime_hash with cli-cache-acquire (Cache 1B-a), where a clone cannot pin mtimes. Neither exists until then; see the normalize.py section of plan-2026-08-28-cli-first-delivery-map.md.
