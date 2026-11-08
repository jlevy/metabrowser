---
type: is
id: is-01m6y741059kycgwascp802y3g
title: Generate valid cache validators for Unicode paths
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex/browser_gate_prepare
labels: []
dependencies:
  - type: blocks
    target: is-01m5wdbsy6z6d95sgg03kwmm76
parent_id: is-01m6wdjwawp9g1bvnefz2hxze3
created_at: 2026-11-08T18:35:51.162Z
updated_at: 2026-11-08T19:04:24.866Z
---
A read-only probe of exact installed426 confirms build_scoped_etag returns a non-Latin-1 token for a Unicode content identity; Starlette Response header construction raises UnicodeEncodeError. It also leaves an interior quote/newline unescaped for those identities. api_rollup builds its identity from the native served root and query path, so valid non-Latin-1 root/folder names may reach this helper. The completed DATA run's two invalid-byte path500→404 differences only bypass the old ETag failure via absent-path preflight; they do not prove valid Unicode headers safe. Confirm actual valid-root route behavior in a fresh isolated context, then choose a focused fix that preserves opaque, stable, build-scoped cache validation and304 behavior. No compatibility alias or source change yet. Preserve original426 evidence and separately qualify the corrected build before release.
