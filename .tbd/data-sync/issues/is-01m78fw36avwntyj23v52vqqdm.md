---
type: is
id: is-01m78fw36avwntyj23v52vqqdm
title: Managed package plugin environments
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:12.777Z
updated_at: 2026-11-12T21:17:49.784Z
---
Phase 5 (plan: Lifecycle, Managed packages). metab-plugins --install REQUIREMENT creates a uv project per package under a new data home, locks it with the 14-day cool-off applied to every package unless the user names exemptions with --exclude-newer-package (the repository's first-party list does not carry over), syncs --locked into a new directory, checks it, swaps it in, keeps the previous for rollback; --upgrade and --uninstall; the user's uv for a CLI install, the app's for an app-managed runtime. Golden with an offline install from a local wheel.

## Notes

Body rewritten 2026-11-12 after the Fable 5.2 design review; it supersedes the earlier review notes. The plan's Key Decisions are awaiting the owner.
