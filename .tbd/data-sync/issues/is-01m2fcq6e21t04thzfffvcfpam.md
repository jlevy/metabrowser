---
type: is
id: is-01m2fcq6e21t04thzfffvcfpam
title: "PR #117 review S3: build_version git status must not take optional locks"
kind: task
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m2fcq020gq0zzxgs62nrz5rp
created_at: 2026-09-14T07:22:18.433Z
updated_at: 2026-09-14T07:47:50.020Z
closed_at: 2026-09-14T07:47:50.019Z
close_reason: "S3 applied in da00abc5 (PR #117): status --no-optional-locks and describe without --dirty (which rewrites the index regardless); unchanged-index test."
resolution: null
duplicate_of: null
---
src/metabrowser/build_version.py: git status --porcelain can take and refresh index.lock because _git strips GIT_OPTIONAL_LOCKS. Pass --no-optional-locks. PR #117.
