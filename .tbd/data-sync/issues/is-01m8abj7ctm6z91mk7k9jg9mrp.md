---
type: is
id: is-01m8abj7ctm6z91mk7k9jg9mrp
title: "PR #854 A3: Another client's poll can evict a page's comparison, leaving no button"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/research/research-2026-11-22-annotated-collections-and-guided-pr.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m8abhzp7e78ayr7ht6gn8t27
hold: null
hold_until: null
created_at: 2026-11-25T22:00:05.785Z
updated_at: 2026-11-25T22:34:25.885Z
started_at: 2026-11-25T22:34:25.411Z
closed_at: 2026-11-25T22:34:25.884Z
close_reason: "Fixed in f2c147da0 and 19ce529e1: the last-write memo includes the pair held, so each page keeps its own; an answer without moved adopts a same-look comparison or offers any other at once; a guide step refused as stack_moved reads the stack now."
resolution: null
duplicate_of: null
---
Review A on #854: https://github.com/jlevy/metabrowser/pull/854#pullrequestreview-6065545213
