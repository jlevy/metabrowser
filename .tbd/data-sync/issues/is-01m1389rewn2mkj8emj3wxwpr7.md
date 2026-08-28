---
type: is
id: is-01m1389rewn2mkj8emj3wxwpr7
title: "Cache goldens: layout, acquisition, crash recovery, and URL grammar"
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-28T03:58:28.818Z
updated_at: 2026-08-28T03:58:28.818Z
---
Four tryscript sessions proving the cache end to end with no browser and no network. cli-cache-layout: home creation, f01 record, CACHEDIR.TAG, future-format refusal. cli-cache-acquire: clone from a local origin, publish, and a second open that reuses with no network. cli-cache-recover: interrupted publish quarantines, and the startup sweep reclaims staging. cli-url-open: the grammar accepts and rejects with reasons. Hermeticity comes from METABROWSER_HOME pointing into the sandbox plus GIT_CONFIG_GLOBAL and GIT_CONFIG_SYSTEM set to /dev/null. Origin repositories are built with pinned identity and dates so commit SHAs are identical across runs and machines, and goldens assert real revisions rather than [REV] placeholders. cli-cache-recover is the one to insist on: crash recovery is the behavior most likely to be wrong and least likely to be exercised by hand.
