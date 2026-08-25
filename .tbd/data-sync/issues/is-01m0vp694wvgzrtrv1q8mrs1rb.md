---
type: is
id: is-01m0vp694wvgzrtrv1q8mrs1rb
title: Make regular source syntax highlighting uniform and measured
kind: feature
status: in_progress
priority: 1
version: 2
labels:
  - browser
  - syntax-highlighting
dependencies: []
created_at: 2026-08-25T05:27:19.451Z
updated_at: 2026-08-25T05:27:24.146Z
---
Audit and fix syntax highlighting across every regular source surface. Ensure lazy Source tabs for Markdown and structured YAML/JSON receive the same safe progressive enhancement as initially mounted text views; reconcile the browser-readable extension set with the vendored Highlight.js grammar registry; make partial previews highlight the loaded prefix while it remains within one measured byte budget and withdraw color uniformly only after that loaded budget is exceeded; preserve incremental loading, exact text, copy, mount/disposal, and plain fallback behavior. Export the configured limit and language registry through the existing settings boundary with no duplicate constants. Measure representative grammars in a real browser before changing the bound. Add focused unit/DOM/server tests, real-browser validation, CHANGELOG coverage, and update the engineering/architecture documentation with a maintained invariant or check that prevents future drift. Scope is regular source views plus shared highlighting policy; do not add grammars or dependencies.
