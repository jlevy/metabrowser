---
type: is
id: is-01m2fc51sej9ssta3fet8g2h6p
title: "PR #116 review S2: correct the PR body and the plan's normalization table"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m2fc4y836btjbcn5xa0skzp3
created_at: 2026-09-14T07:12:23.853Z
updated_at: 2026-09-14T07:29:21.482Z
closed_at: 2026-09-14T07:29:21.480Z
close_reason: "Applied in 85fc77d1 (PR #116): PR body corrected (four deleted, one renamed; test count); plan table gains <CURSOR>/<ELAPSED> rows and drops the unimplemented pack-files row."
resolution: null
duplicate_of: null
---
PR #116 body says five tests deleted (four deleted, one renamed). Plan table lacks <CURSOR>/<ELAPSED> rows and keeps a pack-files-omitted rule normalize.py does not implement.
