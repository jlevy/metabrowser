---
type: is
id: is-01m8d0zhptym321fypxh234w8h
title: "Show whether a chip is clickable: a hover fill for clickable chips, no hover for static ones, never an underline"
kind: bug
status: closed
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/911
    at: 2026-11-27T00:19:37.722Z
delegate: claude-code@vm
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-26T22:52:51.289Z
updated_at: 2026-11-27T09:49:14.736Z
started_at: 2026-11-26T22:53:11.013Z
closed_at: 2026-11-27T09:49:14.736Z
close_reason: Merged to main as jlevy/metabrowser#911. Follow-ups mb-kcwa (narrow readiness glyph hover) and mb-i547 (selected chip contrast).
resolution: null
duplicate_of: null
---
Owner asked 2026-11-26. Some chips that show check failures underline on hover: the pull request page's readiness badge is a link to the Checks tab inside .github-pull-header, whose rule 'a:hover { underline }' reaches it. Rule to adopt across the design system, following GitHub's Primer (interactive tokens change background on hover; labels and state badges are static): a clickable chip (a link or button, or the whole content of one) has a pointer cursor, never an underline, a background change on hover from one shared overlay token, and the focus ring; a static chip or badge has no hover change and no pointer. Inventory every chip-like atom (filter chips, ref chips, GitHub labels, state/review/check/readiness/requirement badges, count and size chips, image fallback chips, table chips, stack chips), fix each, document the rule in docs/design-system.md, and hold it with a Chrome test that hovers every chip found on real surfaces.
