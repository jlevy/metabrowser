---
type: is
id: is-01m1389rewn2mkj8emj3wxwpr7
title: "Cache goldens: layout, acquisition, crash recovery, and URL grammar"
kind: task
status: closed
priority: 1
version: 18
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2kwk6h6pzxanejy6c339r08
  - type: blocks
    target: is-01m2p1pshr699c6pf8xqeer16j
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
child_order_hints:
  - is-01m2s7p36wwz4jjvvyv4x70mq7
hold: null
hold_until: null
created_at: 2026-08-28T03:58:28.818Z
updated_at: 2026-09-23T05:32:39.586Z
started_at: 2026-09-16T21:10:44.821Z
closed_at: 2026-09-23T05:32:39.584Z
close_reason: "Done on codex/v012-foundation-stabilization (PR #226; bb6888b2, a4f2043c, e229f5cf). New goldens: cli-cache-interrupt-store, cli-cache-interrupt-alias, cli-cache-fetch-failures, cli-cache-url-grammar (real-subprocess tryscript), cli-cache-unsupported-git, cli-cache-repair-guidance, cli-cache-readonly-miss, and the live acquire golden cli-cache-acquire-live, green on real Git 2.43.7 and 2.50.1. Narrowed by design: interruption during CAS ref publication moves to mb-jlon (publish_refs does not exist before Phase 2B), and auth-isolated fetch failures move to mb-s1lt (file:// has no credentials). Both are noted on those beads."
resolution: null
duplicate_of: null
---
Golden sessions prove Phase 1A and 1B-a with no browser or network: owner-only f01 source/store layout and future-format refusal; deterministic file:// acquisition into one worktree-free store; source alias as the final visibility commit; a second offline cache hit; interruption before store publication, between store and alias publication, and during CAS ref publication; orphan-store reclamation; URL grammar; and source/auth-isolated fetch failures. Hermeticity uses isolated METABROWSER_HOME and null global/system Git configs. Concurrent immutable revision subjects belong to mb-z335 and mb-hoae. Assert deterministic OIDs and logical state, never pack filenames.

## Notes

Partial goldens exist on #217: cli-cache-acquire, orphan-reclaim, readonly-hit, recover.
Still missing from this bead: interruption before store publication, between store and alias, during CAS ref publication, URL-grammar golden, source/auth-isolated fetch failures, unsupported-Git and repair-guidance goldens named in the repo-library Phase 1B-a checklist.
Do not close until those sessions exist or the checklist is deliberately narrowed.
