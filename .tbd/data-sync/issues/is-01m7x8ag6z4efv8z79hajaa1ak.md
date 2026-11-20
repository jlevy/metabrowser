---
type: is
id: is-01m7x8ag6z4efv8z79hajaa1ak
title: The f03 migration refuses a cache with more than 10,000 sources or stores
kind: task
status: open
priority: 4
version: 1
labels: []
dependencies: []
parent_id: is-01m7x1jaewjm2pnxm8dnmnqdtq
created_at: 2026-11-20T19:53:19.326Z
updated_at: 2026-11-20T19:53:19.326Z
---
From the senior review of #666 (A9). The migration lists sources/ and repository-stores/ with max_entries=MAX_MIGRATED_ENTRIES (10,000, the bound the cache routes list under), so a home past it raises ListingLimitError out of open_cache. The routes refuse the same home, but acquisition does not, so such a home can be used today and cannot be migrated. Page the migration's directory scans (or process by chunks) if a home that large exists; none is known.
