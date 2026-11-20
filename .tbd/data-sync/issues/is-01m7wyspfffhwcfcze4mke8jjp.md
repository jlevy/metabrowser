---
type: is
id: is-01m7wyspfffhwcfcze4mke8jjp
title: "Untrusted Markdown in the inert render child: follow-ups from #527"
kind: epic
status: open
priority: 3
version: 13
labels: []
dependencies: []
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
child_order_hints:
  - is-01m7p7s1qphz27kfk9cj68657y
  - is-01m7p7s2kagrx7ab2m94xbaf8n
  - is-01m7p7s3a5fy3117b6p9shxkne
  - is-01m7p7s3wgrhfabg0tgmr8bjtg
  - is-01m7p7s4fat32eawdj82gjyxrx
  - is-01m7p7s4z2gjfb9ywfj1e4skem
  - is-01m7p7s5evvykkgdjyhzgftpg7
  - is-01m7p7s60zkn1zg44w3kxrvkrf
  - is-01m7p7s6jyp4kd7tj164p1tqgz
  - is-01m7pqq2tsh0qgb3a3r0h04qfe
  - is-01m7pqq391y9mn19ezccbstp22
  - is-01m75fzpspek15x7d5dqhnc2yw
created_at: 2026-11-20T17:06:51.500Z
updated_at: 2026-11-20T17:16:41.210Z
---
PR #527 renders untrusted Markdown in the Markdown child under a wall-clock deadline. Its reviews left eleven follow-ups: the refusal's wording and a golden for it (mb-tjyr, mb-xfl2), SDK helpers for render refusals (mb-jl0o), the worker's name (mb-vnt5), a Chrome check on a served pin (mb-gy83), the child's allowlisted environment and resource limits (mb-ff5p), the raised text-preview bound (mb-pfsi), KPress's cache bound by measured size (mb-fudc), a process group for the server's other asyncio children (mb-zj37), and the deadlines for /api/kpress/export and the projection thread (mb-fpqp, mb-dhum).
