---
type: is
id: is-01kzz03fwfcvam3ft3zvfwqx7g
title: "Phase 1B: Resolve standard Markdown links and resources"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz03g4npz4pma4px6mdq2s0
parent_id: is-01kzyxv1db2hhw2ncc20kdr8mp
created_at: 2026-08-14T02:02:35.278Z
updated_at: 2026-08-14T02:04:47.368Z
---
Enhance completed KPress mounts through focused Markdown-plugin modules: resolve bare, dot, parent, served-root, fragment, query, folder, reference-style, raw-HTML, and resource targets exactly; emit canonical hrefs and safe raw URLs; preserve external and native click variants; block unsafe results; retain the normal not-found state on exact open; deliver async fragments; and dispose listeners and pending work. Do not add fuzzy, implicit-extension, site-generator, or per-link preflight behavior. Add resolver and DOM lifecycle tests; run make verify.
