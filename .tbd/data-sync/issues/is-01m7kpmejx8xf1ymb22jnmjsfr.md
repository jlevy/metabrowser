---
type: is
id: is-01m7kpmejx8xf1ymb22jnmjsfr
title: "CI speed 1.3: add devtools/run_goldens.py and run the tryscript goldens four files at a time"
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m7kpmf2bmaqx2fy8f3ytp3yq
  - type: blocks
    target: is-01m7kpnbgvh17pnc0z229034gd
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
hold: null
hold_until: null
created_at: 2026-11-17T02:51:01.084Z
updated_at: 2026-11-17T04:43:50.049Z
started_at: 2026-11-17T04:33:34.637Z
closed_at: 2026-11-17T04:43:50.049Z
close_reason: "Committed 9d56a5b9: devtools/run_goldens.py runs one tryscript run per golden from GOLDEN_JOBS workers (default 4), prints each file's output whole and a golden: line, fails on a missing verdict or no match; make test uses it with the Makefile's TRYSCRIPT. Local pair 2026-11-17: 82 files, 457 commands, 307 s at 1 job and 81 s at 4, identical verdicts. The CI runs of the PR repeat the comparison."
resolution: null
duplicate_of: null
---
Phase 1 of plan-2026-11-16-fast-ci.md. The goldens take 197 s (3.13) to 258 s (3.14t) at the median, 0.43 to 0.57 s a command, one command at a time; tryscript 0.3.1 has no option to run files concurrently. The runner takes one 'tryscript run <file>' per golden from a queue of GOLDEN_JOBS workers with the environment the TRYSCRIPT Makefile variable sets, prints each file's output whole, records each file's time, and fails unless every file of the glob reported a verdict. Accept over 10 runs: all commands pass and each file's verdict equals a run with GOLDEN_JOBS=1. If two goldens share state outside their sandboxes, fix the golden or keep GOLDEN_JOBS=1. An option upstream in tryscript (first-party) is the alternative.
