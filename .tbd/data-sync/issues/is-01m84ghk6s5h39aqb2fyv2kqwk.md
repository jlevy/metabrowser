---
type: is
id: is-01m84ghk6s5h39aqb2fyv2kqwk
title: "cli-git-pin-rollup golden fails locally: the clone prints progress lines on stderr"
kind: bug
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-23T15:31:41.400Z
updated_at: 2026-11-25T02:32:04.979Z
---
On this Mac, tests/test_cli_git_pin_golden.py::test_golden_pin_rollup_and_catalog fails on origin/main (889f47752, 2026-11-23). The catalog step's stderr gains 'cloning <ORIGIN> into <HOME>' and 'cloned <ORIGIN> in 0.0 s', which golden/cli-git-pin-rollup.txt does not have. CI passes it. Probably an environment difference, such as the local Git version (compare mb-tejh) or a cache that is already warm. Find why the clone line appears here and either normalize it or make the run deterministic.
