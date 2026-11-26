---
type: is
id: is-01m78fw36avwntyj23v52vqqdm
title: Managed package plugin environments
kind: task
status: open
priority: 4
version: 7
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
assignee: null
delegate: null
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-12T18:21:12.777Z
updated_at: 2026-11-26T08:37:20.291Z
started_at: 2026-11-26T08:35:34.393Z
---
Phase 5 (plan: Lifecycle, Managed packages). metab-plugins --install REQUIREMENT creates a uv project per package under a new data home, locks it with the 14-day cool-off applied to every package unless the user names exemptions with --exclude-newer-package (the repository's first-party list does not carry over), syncs --locked into a new directory, checks it, swaps it in, keeps the previous for rollback; --upgrade and --uninstall; the user's uv for a CLI install, the app's for an app-managed runtime. Golden with an offline install from a local wheel.

## Notes

2026-11-26: deferred out of the plugin sources plan by its second revision. An environment the user makes with uv and registers with metab --plugins-add does the same job without a fourth home or an installer inside Metabrowser. Kept open for the owner to close or re-plan.
