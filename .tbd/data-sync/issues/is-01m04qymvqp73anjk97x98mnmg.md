---
type: is
id: is-01m04qymvqp73anjk97x98mnmg
title: Bump PLUGIN_SDK_VERSION to 0.2 for the removed openPath surface
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-16T07:35:34.518Z
updated_at: 2026-08-16T07:35:49.998Z
closed_at: 2026-08-16T07:35:49.997Z
close_reason: "Fixed in bdb9ad2 on the PR #49 branch; merge with main verified green"
---
Found in PR #49 review: the branch removes mb.openPath and the metabrowser:open-path event — a breaking SDK change its own compatibility audit says the version gate mitigates — but PLUGIN_SDK_VERSION stayed at 0.1, so a stale external plugin passed metab --doctor and loaded, then threw TypeError at click time. Fixed in bdb9ad2: constant to 0.2, every built-in manifest moved in the same commit, omission test now asserts the refusal, docs and CHANGELOG updated (including entries for the previously unrecorded GitHub URL localization, published-route adapters, and new SDK surface).
