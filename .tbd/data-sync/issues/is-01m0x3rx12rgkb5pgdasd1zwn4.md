---
type: is
id: is-01m0x3rx12rgkb5pgdasd1zwn4
title: Measure painted readiness for regular file views
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0x3sawfqnqshvkb4rqz54yq
  - type: blocks
    target: is-01m0x3skec67w78kafbez3xj2d
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T18:43:55.553Z
updated_at: 2026-08-25T18:58:59.453Z
closed_at: 2026-08-25T18:58:59.441Z
close_reason: File selection now awaits connected active-view render, optional handle readiness, and double-frame paint; late handles dispose safely; Markdown and folder Overview expose concrete initial readiness; focused lifecycle, type, Biome, and integration tests pass; plugin docs record the additive contract.
resolution: null
duplicate_of: null
---
Files/functions/interfaces: src/metabrowser/static/app.js measureNextPaint, selectFile, renderFileWithPlugins, renderFile, and mountPluginView; src/metabrowser/static/types.d.ts MetabrowserViewSpec and an optional instance readiness handle; built-in Markdown and folder renderers where their initial async work has a concrete ready boundary; docs/plugins.md and tests covering lifecycle and type contracts. Behavior: file navigation measures envelope decoding, asset readiness, connected active-view mounting, and selection-to-double-animation-frame readiness. mountPluginView returns one awaitable active-mount result, preserves idempotent disposal and late-handle cleanup, and may await an optional handle.ready promise without requiring external plugins to provide one. Nondefault tabs stay lazy. The existing connected-container contract remains; no unsafe generic off-DOM staging. Acceptance: tests demonstrate that selection does not report ready before an async render or handle.ready settles, stale/disposed mounts cannot mutate or retain resources, synchronous views remain immediate, and production labels carry bounded path/kind/view metadata.
