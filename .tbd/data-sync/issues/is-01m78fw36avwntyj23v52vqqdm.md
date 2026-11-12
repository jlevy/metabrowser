---
type: is
id: is-01m78fw36avwntyj23v52vqqdm
title: "Managed package plugin environments: install, upgrade, uninstall"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:12.777Z
updated_at: 2026-11-12T18:21:12.777Z
---
Phase 4 (plan: Lifecycle, Managed packages). --plugins-install REQUIREMENT creates a uv project per package under the runtime's data home (plugin-envs/<id>/ with pyproject.toml and uv.lock), locked with exclude-newer 14 days (first-party exempt per SUPPLY-CHAIN-SECURITY.md), synced --locked into a new directory, checked with the worker's check op, swapped in, previous kept for rollback; --plugins-upgrade and --plugins-uninstall; the user's uv for a CLI install, the app's for an app-managed runtime. Golden with an offline install from a local wheel.
