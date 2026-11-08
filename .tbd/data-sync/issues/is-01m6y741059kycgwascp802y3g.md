---
type: is
id: is-01m6y741059kycgwascp802y3g
title: Generate valid cache validators for Unicode paths
kind: bug
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex/browser_gate_prepare
labels: []
dependencies:
  - type: blocks
    target: is-01m5wdbsy6z6d95sgg03kwmm76
parent_id: is-01m6wdjwawp9g1bvnefz2hxze3
created_at: 2026-11-08T18:35:51.162Z
updated_at: 2026-11-08T23:44:46.778Z
closed_at: 2026-11-08T23:44:46.777Z
close_reason: "Delivered in PR #337 with scoped installed validation, merged-main CI and proof in the delivery notes."
resolution: null
duplicate_of: null
---
A read-only probe of exact installed426 confirms build_scoped_etag returns a non-Latin-1 token for a Unicode content identity; Starlette Response header construction raises UnicodeEncodeError. It also leaves an interior quote/newline unescaped for those identities. api_rollup builds its identity from the native served root and query path, so valid non-Latin-1 root/folder names may reach this helper. The completed DATA run's two invalid-byte path500→404 differences only bypass the old ETag failure via absent-path preflight; they do not prove valid Unicode headers safe. Confirm actual valid-root route behavior in a fresh isolated context, then choose a focused fix that preserves opaque, stable, build-scoped cache validation and304 behavior. No compatibility alias or source change yet. Preserve original426 evidence and separately qualify the corrected build before release.

## Notes

November 8, final c3 delivery (merge pending): PR #337 at c3d093d2d222ddce74568e7c74111e2cc0c57d3f passed normal-hook full make verify in 1438.51 seconds: 4929 Python passes, nine expected skips and 388 goldens, with lint/types, both audits, distribution and installed-wheel smoke checks; filesystem observer zero bytes. All nine PR CI jobs passed in workflow 42518226853. Exact wheel 0.11.1.dev1290+c3d093d2d is installed for both aliases and all three retained previews, with eleven healthy plugins, 45 unchanged pins and 45 served-asset comparisons. Independent reviews A/B/C cover the fixes and D covers the comment-only startup correction; the 175 KB budget remains unchanged. Original failed gate and 426 comparison evidence remain preserved. No merge, quiet performance or owner release acceptance is claimed. Keep this bead open until root reconciles the actual merge. Public references: https://github.com/jlevy/metabrowser/pull/337 and https://github.com/jlevy/metabrowser/actions/runs/42518226853.

Installed built-in-browser Unicode-root check passes: ordinary Treemap renders three files and 279 bytes with actual cells and no header-construction failure. This new-build check supplements the original valid-Unicode-root failure; it does not relabel the historical DATA input.

November 8 actual delivery. Native stack #339 atomically merged PRs #337, #336, #340 and #342 into main a2677882a2281a1e5b622acf4788ded9e5516331 from 23:27:15 to 23:27:18 UTC. Its tree 8d69ce06a4054c4a394248c36ba05e12ddd38fcc matches qualified installed b2fb exactly. All four PRs and merged main passed nine CI contexts. https://github.com/jlevy/metabrowser/actions/runs/42535251691

The reviewed Unicode validator fix landed in #337. Installed c3 Unicode-root Treemap rendered three files and 279 bytes with valid headers. The original failed Unicode request remains preserved at its earlier source identity.
