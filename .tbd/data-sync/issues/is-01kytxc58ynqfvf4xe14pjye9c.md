---
type: is
id: is-01kytxc58ynqfvf4xe14pjye9c
title: Adopt KPress single-theme-input contract once upstream lands (jlevy/kpress#38)
kind: chore
status: closed
priority: 2
version: 5
labels: []
dependencies:
  - type: blocks
    target: is-01kyxcbtp4r61yqbptzc2fsky1
created_at: 2026-07-31T01:42:14.045Z
updated_at: 2026-08-01T01:07:19.645Z
closed_at: 2026-08-01T01:07:19.645Z
close_reason: "Implemented and verified KPress 0.3.0 upgrade: root base-size hook, single resolved-theme input, authoritative manifest loading, upstream numeric table typing, full make verify, live browser QA, and green PR #19 CI."
---
THEME — finish after the next kpress release (fixes jlevy/kpress#38).

Same kpress bump precondition as mb-2rb8 (do both in one branch).

Changes, keyed to what the release actually ships (single data-kpress-resolved-theme input at one scope, symmetric light/dark keying, theme-agnostic embedded SSR):

1. src/metabrowser/static/app.js applyThemeMode(): set ONLY the single resolved attribute the release documents (today it sets data-kpress-theme + data-kpress-resolved-theme on <html> AND loops over every rendered .kpress element re-stamping both). Delete the element resync loop and the mode mirroring.
2. src/metabrowser/static/plugin_sdk.js: stop passing theme_mode/resolved_theme query params to /api/kpress/render (~line 524). If bead mb-cq5z (interim mount-time re-stamp) was implemented in the meantime, delete that too.
3. src/metabrowser/server.py + src/metabrowser/kpress_adapter.py: drop theme params from the render route/adapter if the new kpress render API no longer takes them for embedded output (keep whatever the export/print path still needs — theme.js and baked attrs remain correct for standalone export).
4. Check _SKIP_EMBEDDED_KPRESS_JS = ["theme.js"] in plugin_sdk.js against the release: still required unless upstream made theme.js embed-aware.

VERIFY (this was the reproduced bug): render a doc, then toggle theme while a render is in flight (or manually set stale data-kpress-* attrs on the .kpress element in devtools): the document must follow the app theme in BOTH directions, and getComputedStyle(.kpress).colorScheme must match the palette. Previously, stale-dark attrs left a fully dark doc inside a light app with color-scheme:light.

Also update docs/design-system.md if a theming section is added. make verify: node >=24.18 via fnm (see mb-2rb8).
