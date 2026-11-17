---
type: is
id: is-01m7kpmdd2sqmd8xdkp7nmef7k
title: "CI speed 1.1: add the serial and chrome markers, the --shard option, and their gates; make test still runs everything in one process"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7kpme30x5k8w9nvtdwam8r2
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-17T02:50:59.874Z
updated_at: 2026-11-17T04:07:22.858Z
---
Phase 1 of plan-2026-11-16-fast-ci.md, Tiers Within make test. Two markers for two properties (review A1 of #496): serial means the test measures wall-clock time and needs the machine to itself, and it runs on every interpreter before the merge; chrome means the test drives headless Chrome, and it is the one marker that lets a pull request check a test on one interpreter. tests/conftest.py gives chrome to every test that uses the chrome_profile fixture, which is its only source. A module adds serial by hand, as pytest.mark.serial(reason=...) with the measurement that forced it; tests/test_process_group.py is the first, so its process-group, signal, and thread checks are the serial tier and its one Chrome test is in the Chrome tier. The three pytest tiers are -m 'not serial and not chrome', -m 'serial and not chrome', and -m chrome: a partition by construction. Add --shard=I/N: keep the collected tests whose index in node-ID order is I modulo N, applied after -m. Gates in tests/suite_gates.py: a test that calls require_chrome and is not chrome fails; a chrome marker on a test that does not use chrome_profile fails; a serial marker without a reason fails; a serial or chrome test in an ADMITTED_GIT_TESTS module fails. Accept when pytest --collect-only shows the three tier expressions summing to the whole collection, and the shards of each tier summing to the tier, for N from 1 to 5, with a unit test of the partition and a test for each gate. No workflow file changes.
