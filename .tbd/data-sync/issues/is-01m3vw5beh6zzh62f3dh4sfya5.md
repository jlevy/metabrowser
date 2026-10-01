---
type: is
id: is-01m3vw5beh6zzh62f3dh4sfya5
title: "v0.12 landing: two verifications owed on a quiet machine (wall-clock startup pairs; single-command golden-update no-op)"
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
created_at: 2026-10-01T13:58:45.967Z
updated_at: 2026-10-01T13:58:46.830Z
---
This machine was loaded by unrelated jobs (load average 50-200) through the stabilization work, so two verifications could not be taken honestly. (1) Wall-clock startup pairs against main: instructions retired show --show 1.038x, --api 1.034x, --version 0.996x, server spawn to first /api 1.026x (PR #254, exp-037), but wall-clock pairs were noise. Run on a quiet machine (load near the core count or lower), from the stack tip: 'UV="uv --config-file uv.toml run --frozen python"; $UV explorations/performance-loop/startup_pairs.py run --tree <folder> --pairs 9 --out .bench/startup-pairs.jsonl --control <v0.11.0 env>/bin/metab --candidate tip=<tip env>/bin/metab; $UV explorations/performance-loop/startup_pairs.py summarize .bench/startup-pairs.jsonl --candidate tip --suffix _ms --ratios'. Accept rule (the user's policy): back-to-back pairs judged per adjacent pair, 1.1x careful tolerance for CLI cold start and server spawn; never 2x. Record the result in exp-037 and the QA record. (2) 'make golden-update' as one command on the clean stack tip must exit 0 and leave 'git status --short' empty; under load it timed out in tryscript three times, though its parts (recorders, drivers, tryscript compare, fixup) were each verified. Also worth doing then: the visible-window performance gate capture on project-10 (explorations/performance-loop/run.py), which was run headless on project-1.
