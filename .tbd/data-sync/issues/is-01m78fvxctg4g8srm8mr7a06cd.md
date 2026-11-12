---
type: is
id: is-01m78fvxctg4g8srm8mr7a06cd
title: "Plugin API gate: one version, Cargo's caret rule, read from raw TOML"
kind: task
status: open
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies:
  - type: blocks
    target: is-01m78fvzd8jj1kh0fpm00zt8zk
  - type: blocks
    target: is-01m78fvydw6w45j43phwjtsq5w
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:06.841Z
updated_at: 2026-11-12T21:18:06.814Z
---
Phase 1 (plan: Plugin API Compatibility, Key Decision 8). sdk_version names one plugin API (browser SDK and injected runtime) and follows Cargo's caret rule for 0.x: 0.MINOR.PATCH, additions bump PATCH, breaks bump MINOR; accept the host's MINOR with PATCH <= host; refuse a newer PATCH as needing a newer Metabrowser; today's 0.7 reads as 0.7.0. Read sdk_version from the raw TOML before PluginManifest validates (extra=forbid would otherwise turn a newer manifest's new table into a schema error). plugin_loader/sdk-changes.toml lists changes by surface name, window globals included; refusals and --doctor name the changes; a test requires an entry for the current version. Deprecate only surfaces a named external plugin uses, recorded with that consumer. metab-plugins --sdk-override NAME for authors (per command, never recorded, logged, page banner). Update AGENTS.md, the Standing Compatibility Answers, and CHANGELOG.md in the same pull request.

## Notes

Body rewritten 2026-11-12 after the Fable 5.2 design review; it supersedes the earlier review notes. The plan's Key Decisions are awaiting the owner.
