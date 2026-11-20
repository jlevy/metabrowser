---
type: is
id: is-01m7rab0va18g75gs6ztjmc02a
title: "Icon sizes and check marks outside the stated rules: a branch chip's copy glyph, the menu check marks"
kind: task
status: open
priority: 4
version: 2
labels: []
dependencies: []
parent_id: is-01m7wysf407hkpj5n35r533gzc
created_at: 2026-11-18T21:52:21.352Z
updated_at: 2026-11-20T17:17:21.154Z
---
Found by the icon catalog (mb-k1k7, docs/design-system-icons.md, Known Departures). (1) .git-ref-copy > svg in static/styles.css sets a 12px literal, smaller than --icon-glyph, and design-system.md 'One Glyph Size' lists only .menu-seg svg and the person glyph as exceptions (Branch Chips' padding row even points at One Glyph Size). .menu-seg svg is a stated exception but a 16px literal rather than a token. (2) A filter chip menu's check mark (.chip-menu-check, static/filter-controls.js) is ✓ in --link in a 12px column; a stack menu's current-member mark (.github-pull-stack-current, builtin_plugins/github/pull-page.js) is ✓ in the text's ink in an --icon-glyph column. Decide whether each is a stated exception (then name it at its rule and in the catalog's Size column) or aligns with the rule.
