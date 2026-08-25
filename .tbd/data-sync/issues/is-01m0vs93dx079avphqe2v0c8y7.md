---
type: is
id: is-01m0vs93dx079avphqe2v0c8y7
title: Validate the v0.7.1 release candidate against v0.7.0
kind: task
status: closed
priority: 0
version: 3
labels:
  - release:v0.7.1
dependencies:
  - type: blocks
    target: is-01m0vs998xppzxkycy2b8fd37g
parent_id: is-01m0vs8cjjpcz1h53bz34290n5
created_at: 2026-08-25T06:21:17.628Z
updated_at: 2026-08-25T06:40:18.473Z
closed_at: 2026-08-25T06:40:18.472Z
close_reason: Validated the exact installed v0.7.0 and commit 7eb4157 artifacts on a fingerprinted 123,573-file project-shaped corpus. Five backend pairs were equivalent with an unchanged corpus; three visible browser runs per build passed every hard gate with no Long Tasks, failed fetches, rendered errors, or page exceptions. Recorded exp-017 and its 51 ms first-row caveat.
resolution: null
duplicate_of: null
---
Run make verify, execute the required previous-release performance loop against v0.7.0, commit the experiment and regenerated report, inspect the wheel and changelog delta, and confirm CI is green for the exact candidate commit.
