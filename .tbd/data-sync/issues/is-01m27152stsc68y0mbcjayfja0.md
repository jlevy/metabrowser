---
type: is
id: is-01m27152stsc68y0mbcjayfja0
title: Make CLI and browser routes total for escaped filesystem names
kind: bug
status: closed
priority: 0
version: 3
labels:
  - release-hardening
dependencies: []
created_at: 2026-09-11T01:26:15.092Z
updated_at: 2026-09-11T08:26:20.858Z
closed_at: 2026-09-11T08:26:20.857Z
close_reason: Unified native filesystem names, canonical inventory identities, browser view routes, and commit CLI selections without aliasing literal-percent siblings. POSIX undecodable bytes and slash canonicalization are covered in route, CLI, inventory, browserless, and golden tests; the full suite passes.
resolution: null
duplicate_of: null
---
Final release review found that --show can resolve a POSIX name containing an undecodable byte, then crash when format_view_href encodes the surrogateescaped native name. Align Python native and canonical-identity route formatting plus direct /view decoding with the browser navigation codec, preserve containment, and add CLI/golden and route tests for %FF versus literal %FF names.
