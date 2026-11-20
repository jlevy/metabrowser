---
type: is
id: is-01m7p9wxbnv6essbhr1rask8ve
title: "Print: drop the top bar's print icon; show a print control only on rendered documents with good print support (upper right of a Markdown render's card, so file view and the Overview's README match), optional and off where not wanted, Cmd-P always works; move into KPress as an optional print indicator if that is cleaner"
kind: task
status: closed
priority: 2
version: 8
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/549
    at: 2026-11-20T17:04:52.518Z
delegate: claude-code@spud10
labels:
  - linear
dependencies: []
parent_id: is-01m7wysf407hkpj5n35r533gzc
hold: null
hold_until: null
created_at: 2026-11-18T03:06:10.164Z
updated_at: 2026-11-20T19:12:06.265Z
started_at: 2026-11-18T03:13:08.743Z
closed_at: 2026-11-18T03:47:29.941Z
close_reason: "Implemented in PR #549 (head 7ae2a8d7e); KPress follow-up mb-jue2."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: adf47909-27c1-47f2-88e0-54b966cff832
    linked_at: 2026-11-20T18:00:47.239Z
---
Owner, 2026-11-18 in chat: 'let's drop the print icon on the top bar altogether. it should only appear on the document rendering of a document where we have good print capabilties, so like the upper right corner of the drop shadow box on a markdown render. This will work then for a document view like a mardkown doc or for a rendered readme within the overview page consistently. If necessary, we can update this support to be part of KPress as an optional print indicator. It should not always be there if not desired, but Command-P should always work.'

## Notes

PR #549 (claude/print-on-document, head 7ae2a8d7e): header print button removed; print-indicator.js draws the document's print button in the card corner for the file Document view and the Overview README behind mountRendered({printIndicator: true}). KPress follow-up filed as mb-jue2 (doc-actions does not fit an embed yet). Help unchanged by design (registry-only; Command-P is the browser's), docs/keyboard-shortcuts.md names Command-P.
