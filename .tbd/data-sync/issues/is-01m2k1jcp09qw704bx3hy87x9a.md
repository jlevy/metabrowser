---
type: is
id: is-01m2k1jcp09qw704bx3hy87x9a
title: "Hosted review Phase 0A.5: add the dormant browser ChangeRequest parser"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
dependencies:
  - type: blocks
    target: is-01m2k1jekxjs3avv8x3d1d60fv
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
created_at: 2026-09-15T17:24:24.379Z
updated_at: 2026-09-15T18:47:04.594Z
---
Add src/metabrowser/builtin_plugins/hosted_review/hosted-review-model.js with parseChangeRequest and closed-key semantic helpers matching the Python result. Add tests/dom/hosted-review-model-behavior.js and tests/test_hosted_review_browser_js.py to run the exact shared conformance corpus in both runtimes. Keep the module strict check-JS, DOM-free, fetch-free, and unregistered: no manifest.toml or index.js.

## Notes

Implemented the dormant DOM-free, fetch-free parseChangeRequest module and Node harness against the exact packaged corpus. The parser catches only FormatError and a synthetic Proxy test proves unexpected implementation defects escape.
