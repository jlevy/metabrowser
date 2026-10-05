---
type: is
id: is-01m44e12wy14rfp2m8wsy35nz1
title: Install committed v0.12 candidate locally for release QA
kind: task
status: closed
priority: 2
version: 6
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-10-04T21:44:55.965Z
updated_at: 2026-10-05T06:51:56.796Z
closed_at: 2026-10-04T21:45:16.346Z
close_reason: Replaced uv-managed installation with committed wheel 0.11.1.dev669+cbcd1af0 using locked runtime dependency constraints. Both ~/.local/bin/metab and ~/.local/bin/metabrowser report that version. New invocations use this candidate; pre-existing servers require restart.
resolution: null
duplicate_of: null
---
Replace the existing uv-managed Metabrowser installation with the wheel built from cbcd1af0, retain the repository locked runtime dependency versions, and verify both metab and metabrowser executable paths and versions. User explicitly requested replacement for manual release testing.

## Notes

After PR268 merged, fetched origin and checked out main at 0b016e4b024445668b2c21a385d797701e311c23. HEAD equals origin/main and the merge tree equals previously verified PR head 9f92d2a4. Replaced local tool installation with wheel built from merged main: 0.11.1.dev673+0b016e4b. Both metab and metabrowser report this version; doctor reports all 11 plugins OK. Existing local config change and dependency symlink were preserved. Restart existing servers to load the new build.
