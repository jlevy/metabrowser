---
type: is
id: is-01m75r1yp26px69z6tr09td5xd
title: Give release-rehearsal builds their own bundle id
kind: task
status: open
priority: 4
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T16:46:30.081Z
updated_at: 2026-11-11T16:46:30.081Z
---
Phase 5, optional. Local release rehearsals register io.github.jlevy.metabrowser from build folders, so a LaunchServices lookup by the release id finds them; a distinct rehearsal id keeps lookups to real installs (research-2026-11-11-uv-and-macos-app-install.md).
