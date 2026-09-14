---
type: is
id: is-01m2fcq20k4tmp93y0bjs3azzn
title: "PR #117 review R3: test_build_version _git uses the developer's global and system git config"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m2fcq020gq0zzxgs62nrz5rp
created_at: 2026-09-14T07:22:13.906Z
updated_at: 2026-09-14T07:22:13.906Z
---
tests/test_build_version.py:24-40. Set GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM=1 and author/committer identity after stripping GIT_*. PR #117.
