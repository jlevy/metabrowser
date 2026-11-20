---
type: is
id: is-01m7pbmj503na98d3a3a4jqc3b
title: Parse untrusted front matter in the inert child under a deadline (#542 A5 follow-up)
kind: task
status: open
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/542
    at: 2026-11-20T17:02:00.188Z
labels:
  - linear
dependencies: []
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
created_at: 2026-11-18T03:36:33.695Z
updated_at: 2026-11-20T17:14:56.581Z
---
Off the event loop is not off the GIL: a plain /api/file took 0.7 ms alone and 206 ms beside a 2.3 s load at FRONTMATTER_MAX_BYTES. Move untrusted front-matter parsing into #527's Markdown child under its deadline; lowering the byte bound would refuse real front matter.
