---
type: is
id: is-01m7kpmdd2sqmd8xdkp7nmef7k
title: "CI speed 1.1: add the serial marker, the --shard option, and their gates; make test still runs everything in one process"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7kpme30x5k8w9nvtdwam8r2
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-17T02:50:59.874Z
updated_at: 2026-11-17T02:51:51.894Z
---
Phase 1 of plan-2026-11-16-fast-ci.md. tests/conftest.py marks every test that uses the chrome_profile fixture as serial, and a module may add the marker by hand with the measurement that forced it (tests/test_process_group.py first). Add --shard=I/N: keep the collected tests whose index in node-ID order is I modulo N, applied after -m. Gates in tests/suite_gates.py: a test that calls require_chrome and is not serial fails; a serial module in ADMITTED_GIT_TESTS fails. Accept when pytest --collect-only shows -m serial plus -m 'not serial' equal to the whole collection, and the shards of each tier equal to the tier, for N from 1 to 5, with a unit test of the partition. No workflow file changes.
