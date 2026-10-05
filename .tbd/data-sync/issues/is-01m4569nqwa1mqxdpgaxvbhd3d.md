---
type: is
id: is-01m4569nqwa1mqxdpgaxvbhd3d
title: Make configuration-storage refusal guidance name the configuration override
kind: bug
status: in_progress
priority: 3
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m404jrt4sm3rndr1kznbpr6v
hold: null
hold_until: null
created_at: 2026-10-05T04:49:03.227Z
updated_at: 2026-10-05T05:57:41.274Z
started_at: 2026-10-05T05:57:41.260Z
---
PR 268 review follow-up: shared private-storage and future-format diagnostics still use application-home wording and recommend METABROWSER_CACHE_DIR even when read_config rejects the separate configuration root. Safety enforcement is correct, but changing the cache override does not resolve a configuration-root refusal. Carry storage context into user-facing guidance or use accurate neutral wording; cover configuration permissions and future-format errors without exposing private paths.
