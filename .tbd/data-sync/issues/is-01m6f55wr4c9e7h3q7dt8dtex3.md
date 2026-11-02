---
type: is
id: is-01m6f55wr4c9e7h3q7dt8dtex3
title: A mirror location under home has an unexpanded tilde that breaks a quoted git -C
kind: bug
status: open
priority: 4
version: 1
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-02T22:13:18.715Z
updated_at: 2026-11-02T22:13:18.715Z
---
From the docs pass 2026-11-02, from reading rather than a run on a default cache. /api/source/status reports location with ~ under home by design, so nothing spells out the home directory, but a script that passes it quoted to git -C breaks. The docs tell readers to expand it. Decide whether the field needs a companion or the docs are enough.
