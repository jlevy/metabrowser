---
type: is
id: is-01m7kpme30x5k8w9nvtdwam8r2
title: "CI speed 1.2: add pytest-xdist with its supply-chain review, make the parallel tier pass under it, split make test into test-parallel, test-serial, and test-goldens, and measure the speedup in CI"
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7kpmf2bmaqx2fy8f3ytp3yq
  - type: blocks
    target: is-01m7kpnbgvh17pnc0z229034gd
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-17T02:51:00.575Z
updated_at: 2026-11-17T03:05:25.630Z
---
Phase 1 of plan-2026-11-16-fast-ci.md; needs the owner's answer to Q2. pytest-xdist 3.8.0 (2025-07-01) and execnet 2.1.2 (2025-11-12), MIT, dev group only; record the review in SUPPLY-CHAIN-SECURITY.md. make test-parallel runs pytest -m 'not serial' -n auto --dist loadfile; make test-admitted-git runs under xdist too. Known work: pytest_terminal_summary's gh-guard log is per worker under xdist and must be read from every worker; test_cli_main.py and test_refresh_signals.py probe for a port and then bind it. This step measures the factor the plan assumes (2.5 to 3.2 on four processors): the research brief could not, because the measuring machine's load average was above 250. Accept over 10 CI runs of the pull request: no failure a serial run does not have, and the parallel tier at least 2.3 times faster than the measured 510 s (3.13) to 661 s (3.14t). A test that fails only under xdist is fixed, or marked serial with the failure recorded beside the marker. If the factor is below 2.3, Phase 2 splits the unit jobs in two from the start.

## Notes

2026-11-16: the owner answered plan Q2 yes (relayed by the coordinating session): pytest-xdist 3.8.0 and execnet 2.1.2 may join the dev group under the supply-chain rules.
