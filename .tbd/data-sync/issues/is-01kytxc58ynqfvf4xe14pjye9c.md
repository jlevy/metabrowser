---
type: is
id: is-01kytxc58ynqfvf4xe14pjye9c
title: Adopt KPress single-theme-input contract once upstream lands (jlevy/kpress#38)
kind: chore
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-07-31T01:42:14.045Z
updated_at: 2026-07-31T01:42:14.045Z
---
Upstream https://github.com/jlevy/kpress/issues/38 proposes: CSS reads only data-kpress-resolved-theme at one scope with symmetric light/dark keying; color-scheme travels with the palette; theme.js standalone-only; embedded SSR theme-agnostic. Once released: metabrowser sets the one attribute in applyThemeMode, deletes the per-element resync loop and the data-kpress-theme mirroring, and stops passing theme params to /api/kpress/render. Companion of mb-2rb8 (fonts, kpress#37).
