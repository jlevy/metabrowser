---
type: is
id: is-01m7hhr3n6wpvfm1zpsxjh210t
title: "Release 0.13: release-prep PR (CHANGELOG 0.13.0, QA record, exp-099) and owner approval packet"
kind: task
status: in_progress
priority: 1
version: 4
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-16T06:47:09.221Z
updated_at: 2026-11-23T03:14:00.410Z
started_at: 2026-11-23T03:14:00.397Z
---

## Notes

2026-11-17 coordinator: exp-088 renumbered to exp-099. Rename the 0.13.0 heading to '## 0.13.0' (0.12.0 was tagged as '(unreleased)', breaking its release-notes anchor). Draft at the coordinator's /home/user/wt/coord/release/.

2026-11-17 coordinator: plugin SDK ruling (Fable, /home/user/wt/coord/release/sdk-version-ruling.md): no bump, PLUGIN_SDK_VERSION stays 0.7. .menu-section-label was a private host class; climbing relative URLs out of /plugin-static/<name>/ were undocumented (absolute addresses and ensureKindAssets still work); fileTypes.schemaVersion 5 is the registry's own version (precedent 3->4 in 0.9.0). The release-prep PR rewords CHANGELOG entries at about lines 561-563, 864-869 and 1243-1245, opens the Plugin SDK group with 'remains 0.7', and may rename the stale test_deferred_plugin_asset_lifecycle_is_sdk_0_5.
