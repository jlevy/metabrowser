---
type: is
id: is-01m037qctpds7n1g8r4xp1ta6f
title: Self-embed rendered a full duplicate before the transclusion cycle guard fired
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-navigation-extensions.md
labels: []
dependencies: []
created_at: 2026-08-15T17:32:45.270Z
updated_at: 2026-08-15T17:32:52.166Z
closed_at: 2026-08-15T17:32:52.166Z
close_reason: Fixed and verified in a browser against a self-embedding vault; make verify green.
---
The transclusion cycle guard compares an embed key against its ancestry chain, but the top-level renderer started that chain empty. A note containing an embed of itself therefore rendered one complete duplicate of the document inline before the repeat was caught one level down.

Bounded and safe (the depth, document, byte and time budgets still applied), but visibly wrong output for the self-embed authoring pattern.

Fixed on claude/internal-links-url-scheme-rbz0f5 by seeding the chain with the rendered document's own whole-note key through a shared transclusionKey helper, so a self-embed is a cycle at the first embed. Section self-embeds still resolve normally because their key carries the fragment. Covered by a mount-level assertion on the seeded chain and unit checks on the key format.
