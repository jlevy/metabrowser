---
type: is
id: is-01m2eb9qv8c4rf52j15pcm2j86
title: Simplify catalog, feed, file preview, and Markdown engines per release review
kind: epic
status: open
priority: 3
version: 1
labels:
  - simplification
dependencies: []
created_at: 2026-09-13T21:38:14.503Z
updated_at: 2026-09-13T21:38:14.503Z
---
Simplifications proposed by the release senior reviews. Each would remove a class of bugs found in release review, but each is a refactor that needs its own measured change and should not ride on a release:

Catalog and feed (shell lane):
1. Use the provider's code-point order as the catalog's public order (plain comparison, codePointAt only when surrogates meet at the first difference). Removes run detection, the sort phase, the direct-adoption guard, the Unicode ordering session and its parity row; roughly 250 lines.
2. One mutation engine in known-file-catalog.js: mutate the Map, then one sliced linear merge/compaction per stage shared by direct and staged paths. The removal-range and unbounded-splice bugs were exactly where the two engines diverged; roughly 300 lines. Also charge O(n) merges for non-appendable staged point runs, which still count k.
3. One sequence-numbered change journal with a committed cursor in catalog-feed.js instead of pendingChanges, concurrentMutations, and liveMutations.
4. A small FilePreviewCache object owning the file cache, ETags, and revalidation markers, driven directly by its session, instead of callback helpers that test boolean logic over stubs while app.js wiring goes untested.

Markdown (Markdown lane):
5. Parse wiki syntax inside KPress's markdown-it pipeline (inline rule, heading ids from tokens) instead of the hand-written CommonMark approximation: removes the literal mask, line cursor, output budget, the three Worker files, and the transformed-source POST; roughly 1,300 lines. KPress is first-party.
6. Drop the provider-long identity machinery (stepped membership, per-code-unit charging, reverse-segment trie, suffix state machines): cap catalog path length at core admission and resolve suffixes with endsWith over basename buckets; wiki-resolver.js from about 1,500 lines to about 350.
7. Remove duplicated helpers: isPossiblePublishedRoute/isPublishedRoute, two rawResourceHref variants, media-extension tables, and source-path preparation in links.js vs wiki-resolver.js.
