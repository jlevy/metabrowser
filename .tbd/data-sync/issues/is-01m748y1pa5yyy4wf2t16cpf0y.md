---
type: is
id: is-01m748y1pa5yyy4wf2t16cpf0y
title: Rootless pre-imported spare process with an open verb
kind: feature
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:59.017Z
updated_at: 2026-11-11T03:02:59.017Z
---
Phase 6, measured. Removes the 0.7-1 s spawn floor for cold default-profile roots; binds the root's sticky port when it opens it; replaced after each use. Consolidating several same-trust roots into it only if many warm roots make the 65 MB fixed cost matter and the gates in the topology brief pass.
