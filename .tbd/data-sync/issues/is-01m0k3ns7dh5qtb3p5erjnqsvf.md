---
type: is
id: is-01m0k3ns7dh5qtb3p5erjnqsvf
title: Load Mermaid lazily and add kpressInitDiagrams to the plugin SDK
kind: task
status: open
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0k3nsp5dq8cehgxvwq0t82z
parent_id: is-01m0k3nbmdvy9x8g3r8t9ckzjt
created_at: 2026-08-21T21:29:49.037Z
updated_at: 2026-11-14T18:47:38.423Z
---
Mirror _loadKpressTocModule in static/plugin-sdk.js: dynamically import the vendored Mermaid entry, assign window.mermaid so kpress's hostMermaid() succeeds, then import /kpress-static/<ver>/js/diagrams.js and capture its initKpressDiagrams export. Expose mb.kpressInitDiagrams(container) alongside kpressInitToc and declare it in static/types.d.ts.

Trigger the import from the presence of [data-kpress-diagram="mermaid"] in the mounted container. Do NOT add Mermaid to the eager startup scripts or to optional_script_assets in server.py (the prefetched tier, fetched on every page after first idle): eager loading measured 3,572,296 bytes and 449 ms. static/asset-loader.js (the on-demand tier) loads classic scripts only, so the ESM entry needs a dynamic import here or a module entry in the loader; the spec's open questions record the choice.

Keep kpress's securityLevel strict. Additive SDK change; do not bump PLUGIN_SDK_VERSION, whose gate is exact-match and would force an edit to every built-in manifest for nothing.
