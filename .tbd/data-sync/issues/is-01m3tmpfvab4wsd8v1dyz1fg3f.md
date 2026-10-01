---
type: is
id: is-01m3tmpfvab4wsd8v1dyz1fg3f
title: "v0.12 startup and eager-load cost: measure tiers, trim imports, and confirm wall-clock pairs against main"
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-10-01T02:29:04.473Z
updated_at: 2026-10-01T13:58:47.287Z
started_at: 2026-10-01T04:48:09.070Z
closed_at: 2026-10-01T13:58:47.285Z
close_reason: "PR #254 (exp-037): Git, GitHub and cache imports deferred off the plain-folder start and pinned by a fresh-interpreter import-boundary test (CLI modes, eleven API routes, and the page routes); startup in instructions against main: --show 1.038x, --api 1.034x, --version 0.996x, server 1.026x, no pair above 1.05x. Folder shell startup scripts 173 KB against the 175 KB gate (main 171, stack before 187), with devtools/check_startup_scripts.py in lint-check reproducing the gate metric. View helpers and line gutter are one on-demand file; cold pull and commit pages have fewer sequential requests than before the stack. --doctor is 1.54x by design. Independent review: three P1s fixed. Wall-clock pairs are owed on a quiet machine: mb-67s1."
resolution: null
duplicate_of: null
---
Regression check 2026-09-30 (main 6c278f3f vs tip a896d8fe, 9 back-to-back pairs, instructions retired because load was 48-287): no regression in routes (0.99-1.01x) or memory (1.01-1.04x), but (1) startup does 5-7% more work in every mode including --version (CLI --show 1.068x, --api 1.074x, --version 1.055x, server spawn to first /api 1.05-1.06x; CLI CPU time 1.097x with 4 of 9 pairs above 1.1x), all import cost: plugin_api imports metabrowser.source and capability_types/provider_resources (+165M instr; the capability part is removed by PR #246), diff.adapters.git imports git.tree_source, git.wire, invisible_chars (+275M), server imports source_routes, mirror_refresh, git.content_routes, cache.routes (+510M); 653 modules vs 640 for a plain-folder --show. (2) Eager blocking JS is 1.088x raw / 1.093x gzip: source-line-anchors.js (+25.5 KB) is eager with no recorded measurement for its tier (AGENTS.md: pick a loading tier from measured cost); navigation.js +10.7 KB, app.js +9.5 KB, plugin-sdk.js +6.3 KB. (3) The Markdown plugin loads inert-render.js (4.5 KB) and inert-toc.js (8.2 KB) on a trusted folder; check whether a trusted folder uses them. (4) Wall-clock pairs were unusable under load. Do: re-measure after #246; defer Git/GitHub/cache imports off the plain-folder path where it is simple; measure the line-anchor tier in a real browser and record it beside the constant or move it to prefetched; run the kept pair harness on a quiet machine (scratchpad regress/pairbench.py and analyze.py; if the scratchpad is gone, rebuild from the method in this bead). Accept rule: the user's policy, back-to-back pairs judged per adjacent pair, 1.1x careful tolerance for CLI cold start and server spawn; never 2x.

## Notes

2026-10-01: draft PR #254 (codex/v012-startup-cost, exp-037). Startup in instructions retired, 20 adjacent pairs against main: --show 1.066x -> 1.039x, --api 1.063x -> 1.032x, --version 1.046x -> 0.995x, server spawn to first /api 1.049x -> 1.027x; routes unchanged. source-line-anchors.js is on demand beside the view compositor and inert-render.js/inert-toc.js load only on an inert render (measured in Chrome 152, no layout shift). Eager JS transferred 1.094x -> 1.051x. OPEN: (1) performance-budgets.toml startup_script_transfer_kb = 175, main 171, stack 187, after 180: the stack is over the repo's own hard gate, unnoticed because make verify does not check it; the author is moving Git/GitHub-only code off the eager path and adding a deterministic lint-check for the budget. (2) --doctor is 1.54x by design (cache contract validation added in #246); 1.06x with the check stubbed. (3) Wall-clock pairs still owed on a quiet machine; harness committed at explorations/performance-loop/startup_pairs.py.
