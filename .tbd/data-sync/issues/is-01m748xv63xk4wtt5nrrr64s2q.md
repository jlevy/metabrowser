---
type: is
id: is-01m748xv63xk4wtt5nrrr64s2q
title: "Host mode: ready line after bind, sticky port, stdin token, stdin-EOF exit, idle exit"
kind: feature
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m748xw1h1hx5p0eakfc0afgr
  - type: blocks
    target: is-01m748xvkxpj29cp9p8wr6vg5w
  - type: blocks
    target: is-01m748y1pa5yyy4wf2t16cpf0y
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:52.354Z
updated_at: 2026-11-11T03:03:03.824Z
---
Phase 3, core metab. A JSON ready line printed after bind; a sticky port remembered per root with an OS-chosen fallback; a per-launch token on stdin; exit on stdin EOF; --idle-exit. Generalizes the draft VS Code host design (mb-x4y5); a reference-host test covers it.
