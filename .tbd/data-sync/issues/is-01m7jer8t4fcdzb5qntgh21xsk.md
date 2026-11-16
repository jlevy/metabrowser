---
type: is
id: is-01m7jer8t4fcdzb5qntgh21xsk
title: A Markdown document whose only HTML is a comment gets an html_sanitized diagnostics disclosure
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@macbookpro
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-16T15:14:03.203Z
updated_at: 2026-11-16T18:12:02.002Z
started_at: 2026-11-16T17:32:18.948Z
closed_at: 2026-11-16T18:12:02.001Z
close_reason: "Fixed in jlevy/metabrowser#480: /api/kpress/render moves html_sanitized* diagnostics to sanitizer_diagnostics, so the reader's Diagnostics disclosure no longer appears for a comment. KPress side (stop counting comments and nbsp reserialization): jlevy/kpress#75."
resolution: null
duplicate_of: null
---
Every repository document ends with the standard guideline footer, an HTML comment. `metab . --api '/api/kpress/render?path=docs/browsing-files.md'` reports html_sanitized ('Unsafe raw HTML was removed for this trust mode'), so every such document shows a Diagnostics disclosure above its body. A comment is not unsafe content; drop it silently or do not count it. Seen in the Files hero of PR #452 (retaken without the disclosure). From PR #452 review A6(a): https://github.com/jlevy/metabrowser/pull/452#pullrequestreview-5922214786
