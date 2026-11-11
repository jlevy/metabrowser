---
type: is
id: is-01m75n8tverk8x4ytnfnd3z1m6
title: "Research: uv and uvx for installing and launching the macOS app from Applications"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T15:57:49.804Z
updated_at: 2026-11-11T16:46:31.900Z
---
Whether anyone uses uv or uvx to install or launch a native macOS app, and how that could work while the app lives in /Applications (or ~/Applications) like any other Mac app: discoverable in Finder, Spotlight, Launchpad, and the Dock, with Open With and a stable signing identity. Covers prior art, Gatekeeper and quarantine, signing and TCC identity, LaunchServices registration, updates, and how it fits the metab-first layering. Lands in the research PR jlevy/metabrowser#352.

## Notes

2026-11-11: Brief written: docs/project/research/research-2026-11-11-uv-and-macos-app-install.md (commit a44b9f5b on the research branch, jlevy/metabrowser#352). Follow-ups: mb-92d9, mb-5jr9, mb-56nq, mb-5fp7, mb-nneo; update ownership noted on mb-fl72. Close when #352 merges.
