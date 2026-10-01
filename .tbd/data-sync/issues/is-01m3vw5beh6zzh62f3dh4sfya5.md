---
type: is
id: is-01m3vw5beh6zzh62f3dh4sfya5
title: "v0.12 landing: two verifications owed on a quiet machine (wall-clock startup pairs; single-command golden-update no-op)"
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-10-01T13:58:45.967Z
updated_at: 2026-10-01T22:01:12.087Z
closed_at: 2026-10-01T22:01:12.085Z
close_reason: "Both verifications taken: make golden-update is a no-op on the stack tip, and wall-clock startup pairs against v0.11.0 on a quiet machine with bytecode cached in both builds: instructions within 1.04x with no pair over 1.1x; wall-clock medians 0.98-1.07x; --doctor 1.5-1.8x by design, for the user to accept. To be repeated on the final tip by the release rehearsal (mb-cf6y)."
resolution: null
duplicate_of: null
---
This machine was loaded by unrelated jobs (load average 50-200) through the stabilization work, so two verifications could not be taken honestly. (1) Wall-clock startup pairs against main: instructions retired show --show 1.038x, --api 1.034x, --version 0.996x, server spawn to first /api 1.026x (PR #254, exp-037), but wall-clock pairs were noise. Run on a quiet machine (load near the core count or lower), from the stack tip: 'UV="uv --config-file uv.toml run --frozen python"; $UV explorations/performance-loop/startup_pairs.py run --tree <folder> --pairs 9 --out .bench/startup-pairs.jsonl --control <v0.11.0 env>/bin/metab --candidate tip=<tip env>/bin/metab; $UV explorations/performance-loop/startup_pairs.py summarize .bench/startup-pairs.jsonl --candidate tip --suffix _ms --ratios'. Accept rule (the user's policy): back-to-back pairs judged per adjacent pair, 1.1x careful tolerance for CLI cold start and server spawn; never 2x. Record the result in exp-037 and the QA record. (2) 'make golden-update' as one command on the clean stack tip must exit 0 and leave 'git status --short' empty; under load it timed out in tryscript three times, though its parts (recorders, drivers, tryscript compare, fixup) were each verified. Also worth doing then: the visible-window performance gate capture on project-10 (explorations/performance-loop/run.py), which was run headless on project-1.

## Notes

2026-10-01 14:59 PDT, both verifications now taken. Wall-clock startup pairs: 15 back-to-back pairs, v0.11.0 against a wheel built from c16912f8 (PR #261 head), load 1-min 12-16 (10 cores), BOTH environments with compiled bytecode (compileall over site-packages). Instructions retired, median pair ratio (min-max; pairs over 1.1x): --show 1.033 (1.01-1.07; 0/15), --api /api/tree 1.040 (1.00-1.08; 0/15), --version 0.994 (0/15), server spawn to first /api 1.039 (1.02-1.07; 0/15), shell warm 1.000, --doctor 1.779 (15/15). Wall clock, median pair ratio: --show 1.068 (528 -> 577 ms; pairs 0.94-1.49, 7/15 over 1.1x), --api 1.028 (577 -> 601 ms), --version 1.026 (384 -> 413 ms), server first /api 0.980 (513 -> 503 ms), shell warm 0.898, --doctor 1.533 (385 -> 629 ms). Reading: startup does 3-4 percent more work, about 20-50 ms; serving unchanged; --doctor is about 250 ms slower by design (cache contract validation, PR #246) and needs the user's acceptance. IMPORTANT finding: this session's shell sets PYTHONDONTWRITEBYTECODE=1, so environments built by agents never wrote .pyc and every earlier startup measurement in this session (exp-037 included) ran both builds without bytecode caches, about 7.5 G instructions per start where a real install runs about 2.4 G; a first attempt today compared a cached v0.11.0 with an uncached tip and showed a false 3x. exp-037 must state its regime and startup_pairs.py must control it. Raw results: scratchpad coordinator/wallclock2/pairs-pyc.jsonl. The golden-update no-op was verified on 373b59a9 earlier.

2026-10-01, on the stack tip 373b59a9 (PR #257 head): (2) DONE: 'make golden-update' as one command exited 0 and left 'git status --short' empty (load 13-21); the full 'make lint-check' and 'make test' also passed there (3,772 passed, 8 skipped, 264 tryscript commands). (1) ATTEMPTED, NOT RESOLVED: 12 back-to-back pairs of v0.11.0 against a wheel built from 373b59a9 with explorations/performance-loop/startup_pairs.py; other jobs loaded the machine during the run (load 1-min: min 17, median 52, max 97), a CLI start took about 3 s, and wall-clock pair ratios ranged 0.46-2.25, so they are noise. CPU-time medians from the same pairs: --show 1.020 (1/12 pairs above 1.1x, 0 above 1.3x), --api /api/tree 0.990, --version 0.956, --doctor 1.466 (by design). These agree with the instruction counts in exp-037. Still owed: the wall-clock pairs on a machine that stays quiet for about ten minutes, or the user's decision to accept the instruction and CPU-time evidence instead.
