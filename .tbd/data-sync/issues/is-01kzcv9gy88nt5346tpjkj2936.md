---
type: is
id: is-01kzcv9gy88nt5346tpjkj2936
title: "Quick File parent path: match the filename size and show a trailing slash"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-08-07T00:52:10.311Z
updated_at: 2026-08-07T00:52:10.311Z
---
In the palette result rows the parent path should read at the same size as the filename, and should end with a slash so it is unmistakably the enclosing directory.

- .search-palette-description is var(--ui-small-font-size); it should be var(--nav-font-size), matching .search-palette-label
- the path needs a trailing slash: 'src/metabrowser' -> 'src/metabrowser/'

Implementation note: the provider sets description to path.slice(0, separator) with no trailing slash, and the palette computes labelOffset as description.length + 1 to map fuzzy match ranges onto the label. Appending the slash to the provider string would shift every highlight. Append it at render time as its own text node instead, after the highlighted description, so match ranges stay correct and the slash is still real selectable text.
