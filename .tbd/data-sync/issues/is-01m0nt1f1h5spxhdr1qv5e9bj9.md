---
type: is
id: is-01m0nt1f1h5spxhdr1qv5e9bj9
title: "Overview breakdown: one icon per family, on the family row, not on each extension"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T22:39:09.360Z
updated_at: 2026-08-22T23:55:52.501Z
closed_at: 2026-08-22T23:55:52.500Z
close_reason: "The icon is on the family row now, one per family, painted in the family's own colour; extensions inside a family carry none. Verified in a browser: JavaScript shows one olive icon and .js/.cjs/.mjs/.jsx expand beneath it bare. iconPath from the model is what decides, rather than the view inferring from 'does this row name an extension'. Tinting the tree's icons the same way still needs an icon per family in the registry - mb-xrh8."
---
In the Overview page's File Overview breakdown, the icon is on the wrong row and resolved by the wrong taxonomy.

WHAT IT SHOULD BE: one icon per file family, shown on the FAMILY row, the same icon and the same colour for every extension in that family. Expanding a family lists its extensions with NO icons. That way the Overview, the nav tree, and the palette all say the same thing about what a family is, and the icon reinforces the family selection rather than competing with it.

WHAT IT IS. Confirmed in the running app and in the source:

- `file_type_summary_model.js` builds family rows with `extension: null, iconPath: null` (the `kind: "family"` branch), and extension child rows with `extension: child.key, iconPath: \`x${child.key}\``.
- `distribution_view.js:361` then gates on exactly that: `const showIcon = Boolean(extension) || row.kind === "filename";`

So a family row is the one row that never gets an icon, and every extension row does -- the inverse of what is wanted.

WHY THE ICONS ALSO DISAGREE WITH EACH OTHER. `fileTypeIcon(iconPath)` resolves through `FILE_TYPES` in static/app.js -- the hand-maintained 16-entry extension table, not the 56-family registry. `.js` matches an entry and `.mjs`, `.cjs`, `.jsx` do not, so within one JavaScript family the extensions currently resolve to different icons. This is the same second taxonomy that mb-xrh8 describes for the nav tree.

RELATIONSHIP TO mb-xrh8. Same root cause, different surface, and this one is the smaller half: mb-xrh8 is about the nav TREE taking its icon and colour from the registry, and needs an icon per family (or per group with a family override) added to the registry first. This bead is the Overview panel's row structure. Doing this properly needs the registry to carry the icon, so it is most likely the same change or its immediate follow-on -- but the row-placement requirement is stated here because mb-xrh8 does not state it and would not produce it on its own.

CHECK IT WITH: a folder containing .js, .mjs, .cjs and .jsx. Today the JavaScript family row has no icon and its four extensions show at least two different ones. Afterwards the family row carries one icon in the family colour and the four extensions carry none.
