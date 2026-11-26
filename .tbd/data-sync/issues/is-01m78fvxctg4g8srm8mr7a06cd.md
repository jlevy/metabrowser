---
type: is
id: is-01m78fvxctg4g8srm8mr7a06cd
title: "Plugin API gate: one version, Cargo's caret rule, read from raw TOML"
kind: task
status: open
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
assignee: null
delegate: null
labels: []
dependencies:
  - type: blocks
    target: is-01m78fvzd8jj1kh0fpm00zt8zk
  - type: blocks
    target: is-01m78fvydw6w45j43phwjtsq5w
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-12T18:21:06.841Z
updated_at: 2026-11-26T08:37:20.275Z
started_at: 2026-11-26T08:35:34.367Z
---
Phase 0 (plan: Plugin API Compatibility, Key Decision 8). sdk_version names one plugin API (browser SDK and runtime) and follows Cargo's caret rule for 0.x: 0.MINOR.PATCH, additions bump PATCH, breaks bump MINOR; accept the host's MINOR with PATCH <= host; refuse a newer PATCH as needing a newer Metabrowser; today's 0.8 reads as 0.8.0. Today an addition does not change the version, so a plugin cannot declare the addition it needs. Read sdk_version from the raw TOML before PluginManifest validates (extra=forbid would otherwise turn a newer manifest's new table into a schema error). plugin_loader/sdk-changes.toml lists changes by surface name; refusals and --doctor name the changes; a test requires an entry for the current version. No deprecation window by default: a surface outlives its removal only for a consumer named in sdk-changes.toml, for one release. The override flag of the first revision is dropped. Update AGENTS.md, the Standing Compatibility Answers, arch-plugin-system.md, docs/plugins.md, and a changelog fragment in the same pull request. The build stamp between host and worker is the worker client's (mb-nes2), and is not a version.

## Notes

Rewritten 2026-11-26 with the plan's second revision (review against main); supersedes the 2026-11-12 body.
