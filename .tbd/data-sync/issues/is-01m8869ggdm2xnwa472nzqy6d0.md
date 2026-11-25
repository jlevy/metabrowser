---
type: is
id: is-01m8869ggdm2xnwa472nzqy6d0
title: A Markdown file's valid frontmatter reports a YAML error that quotes HTML markup
kind: bug
status: in_progress
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/816
    at: 2026-11-25T03:10:40.291Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-25T01:49:28.277Z
updated_at: 2026-11-25T03:10:40.303Z
started_at: 2026-11-25T02:05:39.744Z
---
The owner reported (2026-11-24): a Markdown file in a private GitHub repository, viewed in Metabrowser from its github.com blob address, shows a frontmatter_error warning twice (once as a raw type/message/severity dump, once as a Frontmatter error notice): 'Error parsing YAML metadata: mapping values are not allowed here ... line 7, column 92: ... -bead: <id>"></span>bead: <id>'. The file's frontmatter is valid YAML (seven plain keys: title, description, author, date, as_of, status, and bead: <id>; its line 7 is 18 characters long), so the parser was given rendered HTML (a span with an id ending in the line's own text), not the file's bytes. Find the cause and the cleanest robust fix: frontmatter parsed only from the file's source bytes, and the warning shown once and readably.
