---
type: is
id: is-01m82pjfezpdfpc8a6cknpnz2m
title: Reject non-finite weights before allocating CI shards
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m82c8bd5hw5cyz98wty5qm63
created_at: 2026-11-22T22:38:32.922Z
updated_at: 2026-11-22T22:38:32.922Z
---
Independent review of Metabrowser PR #698 found that a hand-edited NaN weight is accepted by the loader and can change partition assignment across Python hash seeds. The checked-in weights and the generator produce finite nonnegative values. Validate loaded weights before partitioning and cover a malformed input.
