---
type: is
id: is-01m0vp694wvgzrtrv1q8mrs1rb
title: Make regular source syntax highlighting uniform and measured
kind: feature
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/done/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels:
  - browser
  - syntax-highlighting
dependencies: []
created_at: 2026-08-25T05:27:19.451Z
updated_at: 2026-08-25T06:18:05.225Z
closed_at: 2026-08-25T06:18:05.210Z
close_reason: Implemented and documented uniform source highlighting with a measured 512 KiB policy; focused browser validation, make format, make verify, pre-push verification, and all five exact-head GitHub checks pass.
resolution: null
duplicate_of: null
---
Audit and fix syntax highlighting across every regular source surface. Ensure lazy Source tabs for Markdown and structured YAML/JSON receive the same safe progressive enhancement as initially mounted text views; reconcile the browser-readable extension set with the vendored Highlight.js grammar registry; make partial previews highlight the loaded prefix while it remains within one measured byte budget and withdraw color uniformly only after that loaded budget is exceeded; preserve incremental loading, exact text, copy, mount/disposal, and plain fallback behavior. Export the configured limit and language registry through the existing settings boundary with no duplicate constants. Measure representative grammars in a real browser before changing the bound. Add focused unit/DOM/server tests, real-browser validation, CHANGELOG coverage, and update the engineering/architecture documentation with a maintained invariant or check that prevents future drift. Scope is regular source views plus shared highlighting policy; do not add grammars or dependencies.

## Notes

Audit found lazy Source tabs missed the shell pass and structured Source depended on an unloaded text plugin. Chromium 141 attached-DOM measurements at 512 KiB: Markdown 340 ms/29,127 spans; YAML 756 ms/62,602; TypeScript 868 ms/50,902; JSON 1,139 ms/170,392. At 2 MiB: 1,477-4,449 ms and 116,509-681,571 spans. Retained 512 KiB, moved enhancement after paint, capped syntax-known initial prefixes, and withdraws highlighting uniformly after cumulative loaded bytes exceed the bound. Implemented one Python extension-and-basename grammar registry checked against every vendored grammar, including path-aware diff resolution and extensionless Makefile/Gemfile/Rakefile handling; shared SDK Source renderer; exact Markdown frontmatter copy/text; and durable development, plugin, architecture, large-content, spec, and CHANGELOG documentation. Real-browser checks pass for lazy Markdown YAML and Markdown spans, structured JSON Source with the text plugin absent, default Python, extensionless Makefile, exact 255-byte Markdown source/copy payload, and no alerts. Final make format and make verify pass: 1,534 tests, 48 golden scenarios, lint and type checks, public hygiene, supply-chain checks, locked audits, distribution inspection, and installed-wheel smoke tests.
