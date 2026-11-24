---
type: is
id: is-01m85krfq24mcmgmjf3qxwwmdj
title: "Rendered diff: a table loses .kpress-table-wrap because withoutRenderWrappers unwraps its only div"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-24T01:47:07.361Z
updated_at: 2026-11-24T01:47:07.361Z
---
withoutRenderWrappers in src/metabrowser/static/inert-html.js unwraps a block's only <div>. A table's KPress wrapper is such a div, so the rendered diff's table never gets .kpress-table-wrap: the code that adds it only does so when the parent is not the prose. A table in a diff therefore lacks the Document view's table wrapper and its spacing and overflow. Likely fix: do not unwrap a DIV whose only element child is a TABLE. Found while measuring mb-6d1s (#780).
