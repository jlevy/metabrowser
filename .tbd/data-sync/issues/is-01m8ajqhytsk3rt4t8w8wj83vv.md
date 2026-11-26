---
type: is
id: is-01m8ajqhytsk3rt4t8w8wj83vv
title: Replace the vendored highlightjs-lean with the port in the shell and tests
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-25-lean-language-support.md
labels: []
dependencies:
  - type: blocks
    target: is-01m8ajqjbrx24d4dwttdbpv9wz
  - type: blocks
    target: is-01m8ajqkwq4ryt1v0d25xkwxdy
parent_id: is-01m8ahev7t0174z3a2vhhnpw81
created_at: 2026-11-26T00:05:20.474Z
updated_at: 2026-11-26T00:05:22.455Z
---
Remove the highlightjs-lean devDependency, lock entry, VendorEntry, manifest record, license file and NOTICE entry; add the port to server.py's prefetched tier, NOTICE (Apache-2.0 derivation), the syntax shim (loads first-party grammars from static/syntax/), test_index_cdn_origins and test_plugin_sdk_helpers. Keep sorry/admit/#exit styled as warnings.
