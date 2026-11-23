---
type: is
id: is-01m83chvd7pwcehje7ssmf38sk
title: Restore Linux TCP_NODELAY on reserved HTTP listening sockets
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m83bbgeajzxhr6xkpabzgs0c
created_at: 2026-11-23T05:02:41.062Z
updated_at: 2026-11-23T05:02:41.062Z
---
Matched-HTTP browser startup on GitHub-hosted Linux retains a repeated 40–41 ms small-asset header/body gap. A prebound listener created with protocol 0 causes asyncio to skip TCP_NODELAY on accepted Linux sockets. Declare IPPROTO_TCP when reserving the port and test the adopted transport. Verify under the pinned 0.12.0 baseline and release candidate after the fix.
