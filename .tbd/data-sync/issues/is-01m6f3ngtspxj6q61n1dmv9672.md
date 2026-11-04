---
type: is
id: is-01m6f3ngtspxj6q61n1dmv9672
title: PR prose ignores the reading width and has mismatched code sizes
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
created_at: 2026-11-02T21:46:53.656Z
updated_at: 2026-11-04T17:14:29.779Z
started_at: 2026-11-02T21:47:08.421Z
closed_at: 2026-11-04T17:14:29.779Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Reported by the owner. Reading Width requires --doc-measure, and code sizes belong to the document's ramp. PR text should read as the same Markdown does in a file; try reusing the md-body path. Proved by a table against the same Markdown in a file.
