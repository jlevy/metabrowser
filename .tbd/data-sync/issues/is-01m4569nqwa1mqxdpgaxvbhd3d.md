---
type: is
id: is-01m4569nqwa1mqxdpgaxvbhd3d
title: Make configuration-storage refusal guidance name the configuration override
kind: bug
status: closed
priority: 3
version: 4
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m404jrt4sm3rndr1kznbpr6v
hold: null
hold_until: null
created_at: 2026-10-05T04:49:03.227Z
updated_at: 2026-10-05T06:42:47.863Z
started_at: 2026-10-05T05:57:41.260Z
closed_at: 2026-10-05T06:42:47.848Z
close_reason: "All PR268 review findings R1-R4 fixed. R4 implemented in c269a95d with assertion follow-up 9f92d2a4. Full make verify passed: 4008 tests, 8 skips, 278 goldens, clean audits and distribution checks. All nine GitHub checks green in run 37272909283; formal review disposition posted. R1-R3 existing beads were already closed."
resolution: null
duplicate_of: null
---
PR 268 review follow-up: shared private-storage and future-format diagnostics still use application-home wording and recommend METABROWSER_CACHE_DIR even when read_config rejects the separate configuration root. Safety enforcement is correct, but changing the cache override does not resolve a configuration-root refusal. Carry storage context into user-facing guidance or use accurate neutral wording; cover configuration permissions and future-format errors without exposing private paths.

## Notes

Addressing PR268 review R4 on codex/v012-loose-ends. Chose accurate neutral wording in the shared security layer, which protects both roots, plus exact storage-specific future-format guidance. Permission and future-config regression checks verify no mutation or path exposure. Focused storage tests: 74 passed; golden drivers: 31 passed. Final full gate and CI pending.
