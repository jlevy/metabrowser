---
type: is
id: is-01m0ghfsk6xez0wthha545z1gn
title: "Git graph: node shape must not depend on highlight state"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-08-20T21:33:29.573Z
updated_at: 2026-08-20T21:47:43.265Z
closed_at: 2026-08-20T21:47:43.264Z
close_reason: "Landed in d84e934: the ring is one evenodd path so the hole is a real hole; node shape is invariant under hover and selection. The three background-copy CSS rules and the ordering test that policed them are gone."
---
Merge nodes render hollow, but the hollow center is filled with a color chosen to match the unselected row background; when a row is hovered or selected the row background changes and the node reads as a different shape. Node shape encodes commit state (merge, HEAD, normal) and must be invariant under selection and hover — draw the hole as a real hole (no fill) rather than a background-colored disc, or otherwise make it track the row's actual background.
