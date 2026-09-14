---
type: is
id: is-01m2f38n8mztavm6vactpfxn04
title: "Markdown: optimistic navigation for explicit-path wiki misses on a truncated catalog"
kind: task
status: open
priority: 3
version: 1
labels:
  - markdown
dependencies: []
created_at: 2026-09-14T04:37:04.915Z
updated_at: 2026-09-14T04:37:04.915Z
---
Follow-up from PR #114 review suggestion 2b (https://github.com/jlevy/metabrowser/pull/114#pullrequestreview-5193705916). On a catalog truncated at the inventory file cap, an explicit-path wiki link such as [[docs/deep/file.md]] that the index does not hold settles as unsupported/catalog-truncated (disabled). /api/file can serve a file the index never reached, so the link could navigate optimistically and rely on the shell's not-found handling for a real miss. This is a UX decision rather than a defect (the reviewer called the conservative choice defensible): decide whether a disabled explanation or a possibly-failing navigation is better, how extensionless explicit paths pick their candidate, and what embeds (![[...]]) should do. Code: src/metabrowser/builtin_plugins/markdown/wiki-resolver.js (the prepared.miss === 'not-found' branch under catalogTruncated).
