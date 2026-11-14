---
type: is
id: is-01m6f6mpqkfzn5g1cawbh028y8
title: A windowed changed-file list past a few hundred files
kind: feature
status: closed
priority: 2
version: 2
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3ne8f25m4n06r3d09zw9d
created_at: 2026-11-02T22:38:52.657Z
updated_at: 2026-11-14T18:45:49.951Z
closed_at: 2026-11-14T18:45:49.950Z
close_reason: "Same work as mb-ivvw: window Files changed's sections past a few hundred files, decided with the changed-files nav (mb-q3jt); exp-040's 611 ms projection of 1,183 sections predates the first-screen mount mb-ivvw records."
resolution: duplicate
duplicate_of: is-01m6fczffs8pdsdktnahd1ked2
---
exp-040: after the fixes, the stress case's remaining 1.1 s is the 611 ms projection of 1,183 sections, and only windowing removes it. Decide with the changed-files nav, mb-q3jt.
