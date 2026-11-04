---
type: is
id: is-01m3vt1xj71w8xd6jfyp38k3fd
title: "Inert Markdown: the server keeps a link scheme's case and the page lowercases it"
kind: bug
status: closed
priority: 4
version: 4
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-10-01T13:21:56.294Z
updated_at: 2026-11-04T17:14:29.743Z
started_at: 2026-11-01T16:05:44.915Z
closed_at: 2026-11-04T17:14:29.743Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Found while adding the hostile-link corpus in PR #258: for a link written 'HTTP://example.com', inert_html.py keeps the scheme's case and static/inert-html.js lowercases it. Both keep the link, and both refuse the hostile schemes in tests/fixtures/inert-html-hostile-links.json, so this is not a safety issue; but the two layers are meant to produce the same markup (the allowlist parity tests compare them), and the corpus uses lowercase for the two kept links to keep exact-markup parity. Make the layers agree (lowercase in both, as URL parsers do) and add a mixed-case kept link to the corpus.

## Notes

2026-11-01: fixed in PR #273, open, CI green at its last read. Close when it merges; its required review has not run.
