---
type: is
id: is-01m78fvxctg4g8srm8mr7a06cd
title: Caret SDK gate, sdk-changes.toml, change-naming refusals, and the author override
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies:
  - type: blocks
    target: is-01m78fvzd8jj1kh0fpm00zt8zk
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:06.841Z
updated_at: 2026-11-12T18:47:15.910Z
---
Phase 1, first PR (plan: SDK Compatibility). Replace strict equality in PluginManifest.validate_consistency with Cargo's caret rule for 0.x: 0.MINOR.PATCH, additions bump PATCH, breaks bump MINOR; accept same MINOR with PATCH <= host; refuse newer PATCH as needing a newer Metabrowser; today's '0.7' reads as 0.7.0. Add plugin_loader/sdk-changes.toml listing additions, changes, and removals by surface name (window globals MetabrowserCharts, MetabrowserTooltip, MetabrowserAssets included), make refusals and --doctor name the changes between the plugin's version and the host's, test that PLUGIN_SDK_VERSION has an entry, and add --plugins-sdk-override NAME (per command, never recorded, logged, page banner). Update docs/development.md Standing Compatibility Answers (plugin APIs row: caret gate, deprecate before removing where cheap) and CHANGELOG.md.

## Notes

Review (2026-11-12, independent design review; plan updated to match): Read sdk_version from the raw TOML and gate before PluginManifest.model_validate, since extra=forbid would otherwise turn a newer manifest's new table into a schema error instead of naming the needed Metabrowser. Deprecation only for surfaces a named external plugin uses, recorded with that consumer in sdk-changes.toml. Update AGENTS.md's PLUGIN_SDK_VERSION rule and the Standing Compatibility Answers in this PR, not later.
