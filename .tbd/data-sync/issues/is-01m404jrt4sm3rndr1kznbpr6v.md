---
type: is
id: is-01m404jrt4sm3rndr1kznbpr6v
title: Decide cache/config directory conventions and environment variable migration
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-10-03T05:42:51.965Z
updated_at: 2026-10-03T05:42:51.965Z
---
Evaluate XDG_CACHE_HOME/metabrowser (default ~/.cache/metabrowser) for disposable cache, separate durable configuration/data locations, and native platform conventions. Clarify or replace METABROWSER_HOME without breaking existing overrides. Inventory durable versus reconstructible records, define migration and precedence, and validate security checks and cleanup semantics. User raised this during release QA; design decision pending, no default-location change authorized yet.
