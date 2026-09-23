---
type: is
id: is-01m2kwk6h6pzxanejy6c339r08
title: "v0.12 GitHub Phase 2A base: verify the integrated format, source, store, and trust prerequisites"
kind: task
status: open
priority: 1
version: 15
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: claude-code@spud10.local
labels:
  - stack:base
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2h7jjga1ge5dzvs913n5fgs
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
  - type: blocks
    target: is-01m2kw2b66x74xxjjtdp3wrsr4
  - type: blocks
    target: is-01m3617625k6h6qq4dq2hyxytb
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T01:16:42.405Z
updated_at: 2026-09-23T02:26:03.000Z
started_at: 2026-09-16T21:12:28.672Z
---
Before Phase 2A starts, record one exact green integration head containing the reviewed shared-mirror design, Phase 0D binding contracts, cache format/acquisition, consolidated source and immutable Git-pin implementation, cache goldens, and content-trust commits inherited from main (#209 and later hardening). Verify every required OID as an ancestor and run make verify. The trust foundation is already landed; no separate unmerged trust layer is required. New URL and pin entrypoints must apply and prove the forced untrusted profile with a populated cache. Add subsequent phase PRs above the current Stack 218 tip; do not merge or release from this gate.

## Notes

Planning handoff: next work is a new foundation stabilization/acceptance PR above the current live Stack 218 tip (#225 at preparation). Existing #217/#216 acceptance and review obligations remain open. Close or explicitly disposition the relevant findings through mb-k900, mb-tsdc and mb-hoae, then record one exact reviewed green integration head here. Acquisition/pin foundation evidence exercises current CLI/content routes; do not require the not-yet-built acquired-HTTP server before Phase 2A. New HTTP/URL entry-point trust and real cold HTTPS opening are Phase 2A acceptance under mb-s1lt/mb-ew38/mb-innz. No new implementation is started by this metadata update.

2026-09-22 prerequisite reconciliation: HTML trust #209 is merged at fd65812b and main security hardening through #224 is an ancestor of current pushed #216 b3c001a9. No new standalone trust layer is needed. Record the final reviewed integration head only after source/pin and acquisition publication obligations close; verify its ancestry, forced untrusted behavior at new entrypoints, populated-cache isolation, and make verify. Future phase PRs extend the existing formal stack.
