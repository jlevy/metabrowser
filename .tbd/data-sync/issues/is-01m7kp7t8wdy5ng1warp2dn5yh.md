---
type: is
id: is-01m7kp7t8wdy5ng1warp2dn5yh
title: Delete the dead tree._dir_tree walker and use the configured scope in folder helpers (R24)
kind: chore
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0r8xt95921dabcddjjm7csf
created_at: 2026-11-17T02:44:07.068Z
updated_at: 2026-11-17T02:44:07.068Z
---
Remove tree.py's unused scandir family and its server.py re-exports, use the runtime's hidden allowlist in _folder_not_indexed, and document the README scan as a host exemption. --walk is mb-iyu7 and the provider package move is mb-ed9h. See docs/project/research/research-2026-11-17-fdu-backend-revisited.md.
