---
type: is
id: is-01m75sak36bbvrc702gp5xjq1s
title: "First run without metab: Install for me with the user's uv or a bundled uv"
kind: feature
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T17:08:41.701Z
updated_at: 2026-11-11T17:08:41.701Z
---
Phase 5, Flow 2 option (ii) (research-2026-11-11-uv-and-macos-app-install.md). A consent sheet lists the downloads, sizes, and destinations; the app runs the user's uv when it is at least the tested version, else a signed uv inside the app, to do uv tool install 'metabrowser>=<min>' in uv's standard locations with the user's uv config and proxies, streaming uv's output; failures show uv's last lines, Retry, and the manual command; Settings offers Reinstall and Remove; uv tool update-shell is opt-in. Gated on the clean-account probe for uv#14893 (the developer-tools dialog without the Command Line Tools).
