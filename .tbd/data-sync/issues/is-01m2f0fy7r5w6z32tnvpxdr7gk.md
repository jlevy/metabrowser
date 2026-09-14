---
type: is
id: is-01m2f0fy7r5w6z32tnvpxdr7gk
title: "PR #114 review R2: a fatal Worker failure rejects every mount's pending preprocessing"
kind: bug
status: closed
priority: 2
version: 2
labels:
  - markdown
dependencies: []
parent_id: is-01m2f0fb55v9h6480r6cfx514k
created_at: 2026-09-14T03:48:37.751Z
updated_at: 2026-09-14T04:45:54.014Z
closed_at: 2026-09-14T04:45:54.013Z
close_reason: "Fixed in de282ce5 by the keep-behavior option: two-reference fatal-failure test plus docs/plugins.md and acquireMarkdownWorkerClient comment. Retry rejected: operation errors are already per request, remaining fatal causes (module load failure, stopped Worker) fail a retry the same way, protocol violations are defects."
resolution: null
duplicate_of: null
---
PR #114 review R2 (Low). src/metabrowser/builtin_plugins/markdown/markdown-worker-client.js:135-150 via :62-74. fail() rejects the active request and every queued request from all references. Fix (pick one): retry other references' queued requests once on a fresh client, or keep behavior with a two-reference test and docs/plugins.md note.
