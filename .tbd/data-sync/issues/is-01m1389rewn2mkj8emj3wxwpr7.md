---
type: is
id: is-01m1389rewn2mkj8emj3wxwpr7
title: "Cache goldens: layout, acquisition, crash recovery, and URL grammar"
kind: task
status: open
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
delegate: null
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2kwk6h6pzxanejy6c339r08
  - type: blocks
    target: is-01m2p1pshr699c6pf8xqeer16j
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-08-28T03:58:28.818Z
updated_at: 2026-09-18T01:31:37.918Z
started_at: 2026-09-16T21:10:44.821Z
---
Golden sessions prove Phase 1A and 1B-a with no browser or network: owner-only f01 source/store layout and future-format refusal; deterministic file:// acquisition into one worktree-free store; source alias as the final visibility commit; a second offline cache hit; interruption before store publication, between store and alias publication, and during CAS ref publication; orphan-store reclamation; URL grammar; and source/auth-isolated fetch failures. Hermeticity uses isolated METABROWSER_HOME and null global/system Git configs. Concurrent immutable revision subjects belong to mb-z335 and mb-hoae. Assert deterministic OIDs and logical state, never pack filenames.

## Notes

Normalizer rules arrive with these goldens (PR #116 review R1): add the <HOME> rule to src/metabrowser/normalize.py with cli-cache-layout (Cache 1A), and the opt-in <MTIME> rule for mtime/mtime_hash with cli-cache-acquire (Cache 1B-a), where a clone cannot pin mtimes. Neither exists until then; see the normalize.py section of plan-2026-08-28-cli-first-delivery-map.md. URL-grammar production replay and CLI accept/reject tests landed with mb-dxmb; remaining golden scope is layout, acquire, recover, and the <HOME>/<MTIME> normalizers. cli-url-open can stay as the CLI-facing grammar transcript if still wanted, but do not re-implement the fixture oracle.
