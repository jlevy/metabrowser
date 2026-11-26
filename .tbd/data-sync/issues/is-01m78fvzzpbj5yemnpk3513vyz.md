---
type: is
id: is-01m78fvzzpbj5yemnpk3513vyz
title: Verify the three downstream plugins from their own environments
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
    target: is-01m78fw11hmhxr4skq16793f7t
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-12T18:21:09.493Z
updated_at: 2026-11-26T08:37:20.282Z
started_at: 2026-11-26T08:35:34.378Z
---
Phase 3 (plan: Implementation Plan, Phase 3; For Libraries That Ship a Plugin). The motivating domain plugin and the two downstream application plugins move to the current SDK version, import metabrowser_sdk, declare their log adapters with [[log_adapter]], and drop their exact Metabrowser pins (the plugin packages' metabrowser==0.12.0 and the library's browser extra), so the consumer workspace no longer locks a Metabrowser for their sake. Verified from their own environments under a uv tool install and in the app, and later as a trusted repository's plugins running confined: hooks, adapters, and assets, with --doctor clean. Code changes land in the plugins' own repositories; this bead tracks acceptance here.

## Notes

Rewritten 2026-11-26 with the plan's second revision (review against main); supersedes the 2026-11-12 body.
