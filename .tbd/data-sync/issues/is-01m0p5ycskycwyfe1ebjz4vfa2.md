---
type: is
id: is-01m0p5ycskycwyfe1ebjz4vfa2
title: The Metabrowser wordmark links to the project on GitHub
kind: feature
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-23T02:07:11.666Z
updated_at: 2026-08-23T02:29:07.669Z
closed_at: 2026-08-23T02:29:07.668Z
close_reason: Fixed on claude/rollup-icon-fixes; verified in a browser.
---
The Metabrowser wordmark is the title of the gear menu (mb-hqth). It is inert: it names the product and does nothing.

Requested: give it back a hover, and make it a link to the project's GitHub page, https://github.com/jlevy/metabrowser.

- A right arrow appears beside the wordmark on hover.
- The arrow must NOT move the text. It appears in space already reserved for it, so nothing reflows on hover -- the wordmark stays exactly where it is, hovered or not.
- Target is the repository's main page, jlevy/metabrowser.

Points to settle:
- The title currently carries `aria-hidden="true"`, because the menu itself already announces the same name. A link is a control and must be reachable and announced, so that has to change -- and it needs a name that says where it goes rather than just "Metabrowser".
- It opens an external site from a local tool: decide target and rel, and be consistent with how the app treats other outbound links if it has any.
- Keyboard: it sits inside a menu with roving focus, so confirm it takes focus in the expected order and shows the arrow on focus as well as hover, the same way the tooltip rule treats focus.
