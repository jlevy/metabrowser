---
type: is
id: is-01m78fvzzpbj5yemnpk3513vyz
title: Verify the three downstream plugins from their own environments
kind: task
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies:
  - type: blocks
    target: is-01m78fw11hmhxr4skq16793f7t
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:09.493Z
updated_at: 2026-11-12T21:17:41.885Z
---
Phase 2 (plan: Implementation Plan, Phase 2; For Libraries That Ship a Plugin). With the injected runtime, the motivating domain plugin and the two downstream application plugins need no import changes. They declare their log adapters with [[log_adapter]] and drop their exact Metabrowser pins (the plugin packages' metabrowser==0.12.0 and the library's browser extra), so the consumer workspace no longer locks a Metabrowser for their sake. Verified from their own environments under a uv tool install and later as trusted repository plugins: hooks, adapters, and assets, with --doctor clean. Code changes land in the plugins' own repositories; this bead tracks acceptance here.

## Notes

Body rewritten 2026-11-12 after the Fable 5.2 design review; it supersedes the earlier review notes. The plan's Key Decisions are awaiting the owner.
