---
type: is
id: is-01m7jer8t4fcdzb5qntgh21xsk
title: A Markdown document whose only HTML is a comment gets an html_sanitized diagnostics disclosure
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-16T15:14:03.203Z
updated_at: 2026-11-16T15:14:03.203Z
---
Every repository document ends with the standard guideline footer, an HTML comment. `metab . --api '/api/kpress/render?path=docs/browsing-files.md'` reports html_sanitized ('Unsafe raw HTML was removed for this trust mode'), so every such document shows a Diagnostics disclosure above its body. A comment is not unsafe content; drop it silently or do not count it. Seen in the Files hero of PR #452 (retaken without the disclosure). From PR #452 review A6(a): https://github.com/jlevy/metabrowser/pull/452#pullrequestreview-5922214786
