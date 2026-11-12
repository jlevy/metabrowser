---
type: is
id: is-01m77dgvfk24xb45wmzjsd99kh
title: "Review D2 on #363: the gate's static server exposes the checkout beyond its benchmark assets"
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T08:20:52.849Z
updated_at: 2026-11-12T08:21:07.596Z
started_at: 2026-11-12T08:21:07.594Z
---
run.mjs's static server fell back to the checkout root for every non-corpus request, hidden and ignored files included; its containment check compared the unresolved path while statSync and createReadStream followed symlinks, and it accepted any Host. Serve an explicit set of benchmark assets and the generated corpus only, contain them after resolving symlinks, and refuse a foreign Host.
