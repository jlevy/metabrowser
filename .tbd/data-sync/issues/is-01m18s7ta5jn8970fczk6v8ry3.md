---
type: is
id: is-01m18s7ta5jn8970fczk6v8ry3
title: Ship one extension-to-family table to the browser
kind: task
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m0ndt127q6zs53zcr5assk5d
created_at: 2026-08-30T07:30:43.141Z
updated_at: 2026-08-30T09:26:08.906Z
---
The client cannot classify a row today. A tree row carries `ext` and nothing else -- no family -- and the payload that carries family data (`type_families`) is a per-folder TALLY of (id, count, size), not a mapping. So the browser has no way to get from `.mjs` to `javascript`.

WHY NOT PUT THE FAMILY ON THE ROW. It is per row, forever, on a payload whose size is the thing the whole load-time campaign has been fighting. The mapping is the same for every row and changes only when the registry does.

WHY NOT THE depth=0 PAYLOAD. The tree renders from the ROW request, which since exp-007 carries no tallies at all. Anything the renderer needs has to be available without one.

SO: one static table, served like any other asset and cached against the registry fingerprint, holding the extension-to-family map plus, per family, its finished light and dark colours and its icon name. Colours arrive finished for the reason `serialize_distribution_colors` already documents -- sRGB cannot hold the target chroma at every hue, and a browser handed an out-of-gamut `oklch()` clips it, moving hue by up to nine degrees, which is more than the separation the palette is built on.

DONE WHEN the asset is generated from the registry, carries a loading tier chosen from its measured size, and a test pins its shape.

## Notes

Done, and smaller than filed: FILE_TYPE_REGISTRY was already shipped in METABROWSER_SETTINGS with each family's extensions, so only the group icon needed adding to the projection. No new asset and no new loading tier. Colours were already there in DISTRIBUTION_COLORS, which is what makes the tree and the bars agree by construction.
