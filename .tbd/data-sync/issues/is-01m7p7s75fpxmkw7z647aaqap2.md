---
type: is
id: is-01m7p7s75fpxmkw7z647aaqap2
title: KPress silently drops a leading --- block from pull request bodies and comments
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7nz91me6818xtzmqzt9zrhs
created_at: 2026-11-18T02:29:11.982Z
updated_at: 2026-11-18T02:29:11.982Z
---
From PR #542 security review B3 (on main too): KPress strips a leading front-matter block by regex on pull request bodies, comments and reviews, so text is lost silently. No YAML is parsed on that path.
