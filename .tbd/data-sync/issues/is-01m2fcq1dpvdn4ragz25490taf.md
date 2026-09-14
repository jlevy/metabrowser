---
type: is
id: is-01m2fcq1dpvdn4ragz25490taf
title: "PR #117 review R2: a Metabrowser copy committed into another repository is annotated with that repository's commit"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m2fcq020gq0zzxgs62nrz5rp
created_at: 2026-09-14T07:22:13.300Z
updated_at: 2026-09-14T07:22:13.300Z
---
src/metabrowser/build_version.py:91-94, docstring :83-84. Require git ls-files --full-name to print src/metabrowser/build_version.py and derive the top level from module.parents[2]. Add a vendored-copy test. PR #117.
