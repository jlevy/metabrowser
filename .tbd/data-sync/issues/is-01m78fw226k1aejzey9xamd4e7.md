---
type: is
id: is-01m78fw226k1aejzey9xamd4e7
title: "macOS app: Settings > Plugins shows sources, with Add and Remove"
kind: task
status: open
priority: 2
version: 8
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
assignee: null
delegate: null
labels: []
dependencies:
  - type: blocks
    target: is-01m8bfx231spr2pvhzetq1j5as
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-12T18:21:11.621Z
updated_at: 2026-11-26T08:37:20.289Z
started_at: 2026-11-26T08:35:34.389Z
---
Phase 2, macOS app (plan: The macOS App). Settings > Plugins exists on main (PluginsPane.swift, PluginInventory.swift, the plugins command in apps/macos/metab-contract.toml). Add sources to what it lists: each source's kind, scope, authority, location, providers, and problems, from the sources field of metab --plugins --json. Add... runs metab --plugins-add --dry-run --json PATH (metadata only), shows a native confirmation with the environment, providers, authority and its sentence, and the hash, then runs metab --plugins-add --expect SHA256 --json PATH; Remove runs --plugins-remove. Restart affected servers after a change through the upgrade-restart path until reload lands. The change follows the app's contract rule: the declaration, the app-contract golden, and a changelog fragment in one commit, a minor release of metab, and a raised MetabRequirement.minimumRelease. No path for an older metab: the version floor refuses it. The repository bar moved to mb-qoh1.

## Notes

Rewritten 2026-11-26 with the plan's second revision (review against main); supersedes the 2026-11-12 body.
