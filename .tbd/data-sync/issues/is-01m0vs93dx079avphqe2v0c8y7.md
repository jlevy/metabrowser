---
type: is
id: is-01m0vs93dx079avphqe2v0c8y7
title: Validate the v0.7.1 release candidate against v0.7.0
kind: task
status: open
priority: 0
version: 2
labels:
  - release:v0.7.1
dependencies:
  - type: blocks
    target: is-01m0vs998xppzxkycy2b8fd37g
parent_id: is-01m0vs8cjjpcz1h53bz34290n5
created_at: 2026-08-25T06:21:17.628Z
updated_at: 2026-08-25T06:21:23.612Z
---
Run make verify, execute the required previous-release performance loop against v0.7.0, commit the experiment and regenerated report, inspect the wheel and changelog delta, and confirm CI is green for the exact candidate commit.
