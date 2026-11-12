---
type: is
id: is-01m78fw226k1aejzey9xamd4e7
title: "macOS app: Settings > Plugins, project trust bar, and restart on change"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:11.621Z
updated_at: 2026-11-12T18:21:11.621Z
---
Phase 3 (plan: The macOS App). A native list from metab --plugins --json; Add... with an open panel, metab --plugins-add --dry-run --json PATH, a native confirmation showing the interpreter, plugins, hooks, adapters, and that plugin code runs with the app's privacy grants, then --plugins-add --yes --json; Remove; the project-trust bar running ROOT --plugins-trust --yes; restarting affected servers after a change through the upgrade-restart path (mb-895s) until reload lands; a LiveMetabTests check that stopping a folder leaves no worker; README sections. Stacks on the macOS app's stack.
