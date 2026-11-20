---
type: is
id: is-01m7p7s5evvykkgdjyhzgftpg7
title: "Inert-render child: honour a raised text-preview bound (#527 B5)"
kind: task
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7wyspfffhwcfcze4mke8jjp
created_at: 2026-11-18T02:29:10.234Z
updated_at: 2026-11-20T17:16:16.136Z
---
Deferred from PR #527 B5: reachable only when METABROWSER_TEXT_PREVIEW_MAX_BYTES is raised past ~48 MiB; pass the bound to the child or answer 413 in both routes.
