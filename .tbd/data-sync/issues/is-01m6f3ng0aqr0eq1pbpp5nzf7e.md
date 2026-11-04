---
type: is
id: is-01m6f3ng0aqr0eq1pbpp5nzf7e
title: PR page uses literal font sizes
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3nf55rm1sjpaagqaph6nr
hold: null
hold_until: null
created_at: 2026-11-02T21:46:52.809Z
updated_at: 2026-11-04T17:14:29.908Z
started_at: 2026-11-02T21:47:07.605Z
closed_at: 2026-11-04T17:14:29.908Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Type Scale forbids them; github/styles.css has 1.5em, 1.35em, 1.2em and 1.1em.
