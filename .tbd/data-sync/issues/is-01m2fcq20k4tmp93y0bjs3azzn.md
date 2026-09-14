---
type: is
id: is-01m2fcq20k4tmp93y0bjs3azzn
title: "PR #117 review R3: test_build_version _git uses the developer's global and system git config"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m2fcq020gq0zzxgs62nrz5rp
created_at: 2026-09-14T07:22:13.906Z
updated_at: 2026-09-14T07:47:47.447Z
closed_at: 2026-09-14T07:47:47.446Z
close_reason: "R3 fixed in da00abc5 (PR #117): test _git isolates global/system config and pins identity; hostile gpgsign test."
resolution: null
duplicate_of: null
---
tests/test_build_version.py:24-40. Set GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM=1 and author/committer identity after stripping GIT_*. PR #117.
