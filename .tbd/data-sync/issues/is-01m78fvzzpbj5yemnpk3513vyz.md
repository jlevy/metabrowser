---
type: is
id: is-01m78fvzzpbj5yemnpk3513vyz
title: Migrate the three downstream plugins to the plugin SDK
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies:
  - type: blocks
    target: is-01m78fw11hmhxr4skq16793f7t
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:09.493Z
updated_at: 2026-11-12T18:21:10.576Z
---
Phase 2 (plan: Implementation Plan, Phase 2). The motivating domain plugin and the two downstream application plugins depend on metabrowser-plugin-sdk (caret range) instead of metabrowser, import the sidekick names from it, declare their log adapters with [[log_adapter]], and are verified from their own environments under a uv tool install: hooks, adapters, and assets, with --doctor clean. The code changes land in the plugins' own repositories; this bead tracks acceptance here.
