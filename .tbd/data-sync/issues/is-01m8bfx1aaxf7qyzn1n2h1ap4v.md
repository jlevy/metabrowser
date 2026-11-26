---
type: is
id: is-01m8bfx1aaxf7qyzn1n2h1ap4v
title: "Plugin authority: confined by default, full only when chosen"
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m8bfx231spr2pvhzetq1j5as
  - type: blocks
    target: is-01m78gmwnk00rz776w8w8k7g9j
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-26T08:35:08.745Z
updated_at: 2026-11-26T09:20:28.190Z
started_at: 2026-11-26T09:20:28.190Z
---
Phase 4 (plan: Key Decision 11, What a Manifest Declares, Trust and Consent). A decision records an authority, confined or full. The bar offers confined; full is chosen in Review or with --authority full and is never a default. A confined worker's grants: read the environment and its base interpreter, the clone, the served folder and scoped folders, and what manifests declare; write the plugin cache folder and a private temporary folder; no network; tools inside the grants. [plugin.authority] in the manifest: environment and read are granted under confined and shown in the consent; network = true or a write entry needs full, the plugin is listed as needing full access, and the others in the clone load. Where no backend works (Linux before 5.13 or with Landlock off, an unknown architecture, a sandbox that cannot nest, Windows) confined is not offered and the consent says the only choice is full access; a clone trusted as confined loads no plugin Python on such a machine. User-added sources are full unless added confined; --plugin-confined for per-command sources and for CI. The two consent sentences are in the plan. Plugin JavaScript is not confined and the consent says so. Depends on the macOS spike's answer for the worker profile. Threat-model rows for the agent-edit threat and its residual, and the sentence in docs/working-with-agents.md.
