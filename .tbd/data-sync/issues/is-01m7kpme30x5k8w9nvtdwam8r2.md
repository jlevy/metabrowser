---
type: is
id: is-01m7kpme30x5k8w9nvtdwam8r2
title: "CI speed 1.2: add pytest-xdist with its supply-chain review, make the parallel tier and test-admitted-git pass under it, split make test into test-parallel, test-serial, test-chrome, and test-goldens, and measure the speedup in CI"
kind: task
status: closed
priority: 1
version: 8
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
created_at: 2026-11-17T02:51:00.575Z
updated_at: 2026-11-17T06:40:31.069Z
started_at: 2026-11-17T04:59:30.067Z
closed_at: 2026-11-17T06:40:31.068Z
close_reason: "Committed fa105e85 (pytest-xdist 3.8.0 + execnet 2.1.2 with the SUPPLY-CHAIN-SECURITY review; test-parallel/test-serial/test-chrome/test-goldens; PYTEST_WORKERS=logical; SHARD; test-admitted-git under xdist; report encoding for workers; gh guard per worker; test_cli_main announced-port fix), d5a05e20 (py3.14 argparse help; test_github_pulls stand-in gh with builtins only), 484a3185 (Phase 1 Measurements). CI run 44026747033, 3 green attempts: parallel tier 2.0/2.1/2.2/2.4x on 3.12/3.13/3.14/3.14t, below the 2.3 bar on three; test legs 13.9-14.7 min vs 20.4-22.2 on main; admitted-git 3.1/3.5 vs 6.4/6.7. The remaining 7 of the plan's 10 runs are a follow-up bead."
resolution: null
duplicate_of: null
---
Phase 1 of plan-2026-11-16-fast-ci.md; the owner answered Q2 yes. pytest-xdist 3.8.0 (2025-07-01) and execnet 2.1.2 (2025-11-12), MIT, dev group only; record the review in SUPPLY-CHAIN-SECURITY.md. make test becomes four targets: test-parallel (pytest -m 'not serial and not chrome' -n $(PYTEST_WORKERS) --dist loadfile), test-serial (-m 'serial and not chrome', one test at a time), test-chrome (-m chrome, one test at a time, SHARD=I/N), and test-goldens (mb-4ub2). Each tier target goes on the .PHONY list and on the order-only '| install' line, since a CI job calls it directly (review A4 of #496). make test-admitted-git runs under xdist too (review A8). Known work: pytest_terminal_summary's gh-guard log is per worker under xdist and must be read from every worker; test_cli_main.py and test_refresh_signals.py probe for a port and then bind it. This step measures the factor the plan assumes (2.5 to 3.2 on four processors): the research brief could not, because the measuring machine's load average was above 250. Accept over 10 CI runs of the pull request: no failure a serial run does not have; the parallel tier at least 2.3 times faster than the measured 510 s (3.13) to 661 s (3.14t); both admitted-git legs green in all 10, with the test count of a serial run of ADMITTED_GIT_TESTS on the same commit. A test that fails only under xdist is fixed, or marked serial with the failure as the marker's reason, which keeps it on every interpreter (review A1). A module in ADMITTED_GIT_TESTS, such as test_refresh_signals.py, is fixed, not marked: test-admitted-git runs it under xdist with no marker filter, and the gate refuses serial there (review B4). If the factor is below 2.3, Phase 2 splits the unit jobs in two from the start.

## Notes

2026-11-16: the owner answered plan Q2 yes (relayed by the coordinating session): pytest-xdist 3.8.0 and execnet 2.1.2 may join the dev group under the supply-chain rules.
