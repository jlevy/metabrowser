---
type: is
id: is-01m44e12wy14rfp2m8wsy35nz1
title: Install committed v0.12 candidate locally for release QA
kind: task
status: closed
priority: 2
version: 5
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-10-04T21:44:55.965Z
updated_at: 2026-10-05T06:19:53.205Z
closed_at: 2026-10-04T21:45:16.346Z
close_reason: Replaced uv-managed installation with committed wheel 0.11.1.dev669+cbcd1af0 using locked runtime dependency constraints. Both ~/.local/bin/metab and ~/.local/bin/metabrowser report that version. New invocations use this candidate; pre-existing servers require restart.
resolution: null
duplicate_of: null
---
Replace the existing uv-managed Metabrowser installation with the wheel built from cbcd1af0, retain the repository locked runtime dependency versions, and verify both metab and metabrowser executable paths and versions. User explicitly requested replacement for manual release testing.

## Notes

Latest local PR268 installation is 0.11.1.dev672+9f92d2a4, including review R4 diagnostic fixes. Both metab and metabrowser versions verified; doctor reports all 11 plugins OK. Wheel built from committed branch and installed with locked runtime constraints. Restart existing servers to load the new build.
