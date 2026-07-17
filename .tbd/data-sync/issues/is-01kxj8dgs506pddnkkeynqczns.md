---
type: is
id: is-01kxj8dgs506pddnkkeynqczns
title: Make uv release commands immune to ambient user configuration
kind: bug
status: closed
priority: 1
version: 7
labels: []
dependencies:
  - type: blocks
    target: is-01kxj87a53xs0p7rnwecgdsfkj
created_at: 2026-07-15T06:46:21.220Z
updated_at: 2026-07-15T06:56:25.092Z
closed_at: 2026-07-15T06:56:25.092Z
close_reason: Explicit repository uv configuration is enforced and verified end to end.
---

## Notes

Hardened every repository-scoped uv/uvx command in Make, hooks, publishing, executable docs, and source examples with explicit --config-file uv.toml. Package policy now rejects bare repository commands; 672-test make -j4 verify and clean synthetic v0.1.0 build/install smoke pass.
