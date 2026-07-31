---
type: is
id: is-01kytxc50epeqws5nmgvfmy4dk
title: "Harden embedded-doc theme sync: stamp current theme at mount; drop baked-attr reliance"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-07-31T01:42:13.770Z
updated_at: 2026-07-31T01:42:13.770Z
---
Reproduced: toggling theme while a KPress render is in flight leaves the inserted .kpress element with stale baked data-kpress-theme/data-kpress-resolved-theme attrs. Because KPress keys dark palettes on attributes but leaves light as the unkeyed default, a stale-dark element renders a fully dark document inside a light app (color-scheme also splits from the palette). Interim host fix (before upstream jlevy/kpress#38 lands): when mounting fetched KPress HTML in plugin_sdk.js, overwrite the baked theme attrs from the current documentElement state (same stamping applyThemeMode does on toggle). Consider also: stop passing theme_mode/resolved_theme to /api/kpress/render (output is theme-agnostic except these attrs — verified by diff). Chrome-side gaps found in the same audit, may split to separate beads: (1) no dark palette for highlight.js syntax colors (vendored github-light only); (2) chart canvases resolve token colors at draw time and do not repaint on theme toggle.
