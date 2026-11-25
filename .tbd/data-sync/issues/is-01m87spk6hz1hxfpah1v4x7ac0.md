---
type: is
id: is-01m87spk6hz1hxfpah1v4x7ac0
title: "/raw resolves a path and then opens it: a swapped symlink can escape"
kind: bug
status: open
priority: 2
version: 2
spec_path: docs/project/architecture/arch-threat-model.md
labels:
  - security
dependencies: []
parent_id: is-01m8898kcprj50strs0xfshvjn
created_at: 2026-11-24T22:09:25.711Z
updated_at: 2026-11-25T02:46:16.996Z
---
Threat model T4. paths_safe._safe_path resolves (following symlinks) and checks containment, then FileResponse opens the path again: a process that can change the served tree between the two can swap in a symlink to a file outside the root (TOCTOU). Open by directory handle with O_NOFOLLOW per component, or open first and check the opened file's real path (fstat dev/inode against the resolved target).
