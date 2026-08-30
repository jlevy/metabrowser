---
type: is
id: is-01m18s7s2f5qzc7hx8stv2sqcb
title: Registry declares an icon per family, with a group fallback
kind: task
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m0ndt127q6zs53zcr5assk5d
created_at: 2026-08-30T07:30:41.867Z
updated_at: 2026-08-30T09:26:08.619Z
---
The rollup registry declares a hue per family and no icon, so the file tree cannot take its shape from the same place it takes its colour. This adds one.

SHAPE. `icon` is optional on a family and required on a group. A family without one inherits its group's, which is what makes 56 families tractable: most of `code` really is one shape, and only the families that read as a distinct format -- tabular, log stream, pdf -- need to override.

That mirrors the rule the tree already follows and states in app.js: icon is the major type, colour is the subtype. Today that rule is implemented twice, against two different taxonomies. After this it is implemented once.

SCHEMA. This is a registry change, so `FILE_TYPE_REGISTRY_SCHEMA` goes v3 -> v4 and every checked artifact regenerates through `devtools/file_type_contract.py --write`. The icon name is validated against the shipped `ICON_SVG` keys by the contract check, so a typo fails `make verify` rather than rendering a blank row.

DONE WHEN the TOML carries an icon on each group, the families that need to differ carry their own, the contract check rejects an unknown icon name, and the regenerated artifacts are committed.

## Notes

Done: groups declare a required icon, families may override, both carried through the projection, the taxonomy runtime and the fingerprint. Icon names are validated against the shipped set by the contract schema -- verified by planting a bogus name and confirming a non-zero exit.
