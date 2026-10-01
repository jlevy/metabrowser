---
type: is
id: is-01m3tmpfvab4wsd8v1dyz1fg3f
title: "v0.12 startup and eager-load cost: measure tiers, trim imports, and confirm wall-clock pairs against main"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-10-01T02:29:04.473Z
updated_at: 2026-10-01T02:29:06.400Z
---
Regression check 2026-09-30 (main 6c278f3f vs tip a896d8fe, 9 back-to-back pairs, instructions retired because load was 48-287): no regression in routes (0.99-1.01x) or memory (1.01-1.04x), but (1) startup does 5-7% more work in every mode including --version (CLI --show 1.068x, --api 1.074x, --version 1.055x, server spawn to first /api 1.05-1.06x; CLI CPU time 1.097x with 4 of 9 pairs above 1.1x), all import cost: plugin_api imports metabrowser.source and capability_types/provider_resources (+165M instr; the capability part is removed by PR #246), diff.adapters.git imports git.tree_source, git.wire, invisible_chars (+275M), server imports source_routes, mirror_refresh, git.content_routes, cache.routes (+510M); 653 modules vs 640 for a plain-folder --show. (2) Eager blocking JS is 1.088x raw / 1.093x gzip: source-line-anchors.js (+25.5 KB) is eager with no recorded measurement for its tier (AGENTS.md: pick a loading tier from measured cost); navigation.js +10.7 KB, app.js +9.5 KB, plugin-sdk.js +6.3 KB. (3) The Markdown plugin loads inert-render.js (4.5 KB) and inert-toc.js (8.2 KB) on a trusted folder; check whether a trusted folder uses them. (4) Wall-clock pairs were unusable under load. Do: re-measure after #246; defer Git/GitHub/cache imports off the plain-folder path where it is simple; measure the line-anchor tier in a real browser and record it beside the constant or move it to prefetched; run the kept pair harness on a quiet machine (scratchpad regress/pairbench.py and analyze.py; if the scratchpad is gone, rebuild from the method in this bead). Accept rule: the user's policy, back-to-back pairs judged per adjacent pair, 1.1x careful tolerance for CLI cold start and server spawn; never 2x.
