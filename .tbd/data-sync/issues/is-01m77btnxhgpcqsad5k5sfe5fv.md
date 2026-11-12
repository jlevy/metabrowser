---
type: is
id: is-01m77btnxhgpcqsad5k5sfe5fv
title: "CI: run the macOS app's native contract tests when server sources change"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T07:51:17.681Z
updated_at: 2026-11-12T07:51:17.681Z
---
From the final review (mb-niod, #363 review C3): .github/workflows/macos-app.yml's trigger filters omit the server sources and dependency manifests, so a CLI-only change skips LiveMetabTests, which check the app's launch flags, announcement parser, identity route, file routes, and the EOF contract against the checkout's server. Include src/metabrowser and the locked-environment inputs in the filters, or run a native contract job unfiltered. Needs the user's approval for a workflow change.
