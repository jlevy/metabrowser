---
type: is
id: is-01kxry3234hgx9hgphz1xsqsmk
title: "Platform A6: expose MtimeCache (or generation-keyed cache) through plugin_api"
kind: feature
status: closed
priority: 2
version: 5
labels: []
dependencies:
  - type: blocks
    target: is-01kxse0wddy6je24t1dm5caber
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:33.764Z
updated_at: 2026-11-14T18:46:18.124Z
closed_at: 2026-11-14T18:46:18.123Z
close_reason: "Superseded: the diff plugin is built-in with its own commit-keyed comparison cache, and third-party plugin Python is moving out of process (mb-xbw3); reopen there if a plugin needs a host cache."
resolution: canceled
duplicate_of: null
extensions:
  linear:
    id: 206e5eb6-d6d6-4397-8bcd-99383c4fb52c
    linked_at: 2026-08-16T08:06:19.925Z
---
Plugins currently build bespoke caches; export the mtime-invalidation machinery for patch/manifest caching.
