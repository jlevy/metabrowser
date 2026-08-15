---
type: is
id: is-01m03tsgc3m7e530qfhpdj92tb
title: "Content typing: record sniff results during the inventory crawl"
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-15T23:05:57.359Z
updated_at: 2026-08-15T23:05:57.359Z
---
Content classification currently runs at view time: metabrowser.content_sniff.sniff_artifact reads a bounded prefix when a file's extension does not settle its type, and FileContext caches the answer for that one request.

The seam for moving this earlier already exists and is unused:

- classify_prefix(prefix) is pure and does no I/O, so a crawl that already holds a file's leading bytes can call it directly.
- FileContext(path, ext, content_class=...) accepts a precomputed verdict, so a view supplied with one never reads.

The work: have the inventory walker classify while it is already touching each file, persist the result alongside the rest of the inventory entry, and pass it into FileContext so view-time reads disappear for crawled files. Decide what invalidates a stored verdict (mtime_hash is the existing identity) and what the answer is for files the crawl has not reached — the view-time path stays as the fallback.

Worth doing when content typing is consulted for more than the text/binary split, or when the per-view read shows up in a profile. Neither is true today.
