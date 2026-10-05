---
type: is
id: is-01m44e12wy14rfp2m8wsy35nz1
title: Install committed v0.12 candidate locally for release QA
kind: task
status: closed
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-10-04T21:44:55.965Z
updated_at: 2026-10-05T05:08:05.250Z
closed_at: 2026-10-04T21:45:16.346Z
close_reason: Replaced uv-managed installation with committed wheel 0.11.1.dev669+cbcd1af0 using locked runtime dependency constraints. Both ~/.local/bin/metab and ~/.local/bin/metabrowser report that version. New invocations use this candidate; pre-existing servers require restart.
resolution: null
duplicate_of: null
---
Replace the existing uv-managed Metabrowser installation with the wheel built from cbcd1af0, retain the repository locked runtime dependency versions, and verify both metab and metabrowser executable paths and versions. User explicitly requested replacement for manual release testing.

## Notes

Refreshed local installation to repaired PR268 commit f67606b7d158afc1800723f1896d96e350394d57 using the built wheel and locked runtime constraints. Both metab and metabrowser report 0.11.1.dev670+f67606b7; doctor reports all 11 plugins OK. Existing server processes require restart to load the new build.
