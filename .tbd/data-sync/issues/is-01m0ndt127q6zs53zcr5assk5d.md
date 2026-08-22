---
type: is
id: is-01m0ndt127q6zs53zcr5assk5d
title: File tree icons and colors are a separate taxonomy from the rollup registry
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T19:05:22.759Z
updated_at: 2026-08-22T19:05:22.759Z
---
Raised in QA: extensions in one rollup family should share an icon and a color.

They do not, because there are two independent taxonomies.

The tree uses FILE_TYPES in static/app.js -- a hand-maintained list of 16 extension matchers resolving to 9 ft-* classes. The folder Overview, Treemap and distribution bars use the file-rollup registry: 56 families, each with its own declared hue. Nothing keeps them in step, and the table's own comment ('append an extension to the list to pick it up') is why it drifted.

Concretely, using the reviewer's own example:

- .js, .ts, .py and .sh all match one entry and share icon 'alignLeft' and class 'ft-code'. So JavaScript, TypeScript, Python and Shell are one shape and one colour in the tree, while the registry gives them four distinct hues (102.08, 253.30, 246.50, and shell's own).
- .mjs, .cjs and .jsx are not in the table at all. They fall through to the generic 'file' icon with no class -- so .js and .jsx, the same javascript family in the registry, get different icons and different colours in the tree. Same for .mts, .cts, .tsx against .ts.
- .json and .toml are classed ft-yaml, so JSON and TOML files are painted as YAML. The registry has json, toml and yaml as separate families with separate hues.

What to do: derive the tree's icon and colour from the registry classification rather than from a second extension list, so a family's identity is declared once. The registry has no icon field today -- family carries id, label, group_id, order, extensions, hue, linguist, linguist_color -- so this means adding an icon per family (or per group, with family override) and having the tree resolve through the same classifier the rollup uses. plugin_sdk.js exposes iconFor/classFor on window.MetabrowserFileTypes, so the SDK surface changes with it.

Note the ordering dependency: doing this makes every tree row take its family's registry hue, which spreads the palette's collisions (siblings mb-oq6j and mb-6g81) from the Overview bars into the file tree. Worth settling the palette first.
