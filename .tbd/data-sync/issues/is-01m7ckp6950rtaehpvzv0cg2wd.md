---
type: is
id: is-01m7ckp6950rtaehpvzv0cg2wd
title: "Image view and open documents: use versioned /raw addresses for replaced images"
kind: task
status: open
priority: 3
version: 3
spec_path: TODO.md
labels: []
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-11-14T08:44:51.365Z
updated_at: 2026-11-20T17:27:26.853Z
---
Follow-up from #426 (versioned /raw URLs): the Image view (builtin_plugins/image) still uses unversioned /raw addresses, so a replaced image there can show stale content, and a Markdown document already on screen keeps its old image until it is entered again. Done when the Image view uses versioned addresses (or revalidates) and an open document picks up a replaced image, measured in WebKit and Chrome.

## Notes

Standalone: a follow-up of the standalone mb-k3au (#426).
