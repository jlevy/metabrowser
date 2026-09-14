---
type: is
id: is-01m2fcq6e21t04thzfffvcfpam
title: "PR #117 review S3: build_version git status must not take optional locks"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m2fcq020gq0zzxgs62nrz5rp
created_at: 2026-09-14T07:22:18.433Z
updated_at: 2026-09-14T07:22:18.433Z
---
src/metabrowser/build_version.py: git status --porcelain can take and refresh index.lock because _git strips GIT_OPTIONAL_LOCKS. Pass --no-optional-locks. PR #117.
