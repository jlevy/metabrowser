---
type: is
id: is-01m2fcq1dpvdn4ragz25490taf
title: "PR #117 review R2: a Metabrowser copy committed into another repository is annotated with that repository's commit"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m2fcq020gq0zzxgs62nrz5rp
created_at: 2026-09-14T07:22:13.300Z
updated_at: 2026-09-14T07:47:47.104Z
closed_at: 2026-09-14T07:47:47.103Z
close_reason: "R2 fixed in da00abc5 (PR #117): source_checkout requires ls-files --full-name to print src/metabrowser/build_version.py; vendored-copy test."
resolution: null
duplicate_of: null
---
src/metabrowser/build_version.py:91-94, docstring :83-84. Require git ls-files --full-name to print src/metabrowser/build_version.py and derive the top level from module.parents[2]. Add a vendored-copy test. PR #117.
