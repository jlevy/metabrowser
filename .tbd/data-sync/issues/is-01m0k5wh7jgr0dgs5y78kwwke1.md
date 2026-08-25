---
type: is
id: is-01m0k5wh7jgr0dgs5y78kwwke1
title: "End-to-end load time: assets, time to first row, server and CLI"
kind: epic
status: open
priority: 0
version: 55
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
child_order_hints:
  - is-01m0k4p13yqdg3yp2c78rawbhz
  - is-01m0k4p1mdy4m20chsyds7c7yw
  - is-01m0k4p20yey7mb3h4t9z4w94j
  - is-01m0k4p2d6xf80tn8qxhx6qavc
  - is-01m0k4p2s7ay3t761z9da84en0
  - is-01m0k5xdka0fyb19aw97wg5v7s
  - is-01m0k5xdzw6kmhd49gfyxjhwhx
  - is-01m0k5xec4q8565zxfs4mr4dsy
  - is-01m0k5xeqm8ab1sm4wddc99ahs
  - is-01m0k5xf3ej2n2b7f3zawg9r1p
  - is-01m0k5xff9wt2byqj2ja6yxmq3
  - is-01m0k5xfv51f1d214g0fytptqs
  - is-01m0k5xg6xhbr1tp13ypkr40fh
  - is-01m0k5xgjk52878pqq338fzf12
  - is-01m0k5xgycxymyreh03tax0t1q
  - is-01m0k5xha8rmnc747e64g6a5wa
  - is-01m0m5vvtarew6gk78b295j1ag
  - is-01m0m5vwhzn3h5bxyy79w3st82
  - is-01m0m5vwxj193b0g8djjf9ba83
  - is-01m0m5vx9874ce110ymnk5a48e
  - is-01m0m5vxnbtymm7d8pq4f0nwbr
  - is-01m0m5vy1d7k3wgz1jaxt90y0w
  - is-01m0ndh3k7bgqg3cwgbqp5k2nw
  - is-01m0ndh42xfzkccjmv9tvecd75
  - is-01m0ndh4fzdxft43xfkwx7kf71
  - is-01m0nhc76fxcrhvxrvtag7w4qr
  - is-01m0nhc7jsejcaqc7ze5rnjeax
  - is-01m0nhc7w21y84z4rzqqj5e70g
  - is-01m0nk23rhp0sq9aspeqdzxhr1
  - is-01m0nw7vg2kzh80g7vvvk1h28q
  - is-01m0nw7vy19mscpp49m1fsqdb1
  - is-01m0nw7wbymprwzy5j1x54r3b7
  - is-01m0nw7ww543gqmwjyvnb33hm6
  - is-01m0nw7xdehb379bqptsdjzq69
  - is-01m0nw8gwp6jrdae5jwz9y8j80
  - is-01m0nw8h8ch2ba2zsvkjqc8kcg
  - is-01m0nw8hkn680qwx3zrxf6qbgq
  - is-01m0pe6pptgaqpk37yyeahhs9t
  - is-01m0pe6q1kyxarxs3dx6hht3zz
  - is-01m0pe6qc93z4m8x0kxefed3p8
  - is-01m0pe6qpyhzne1b8n83mghdyz
  - is-01m0ppz3m2z464j1m2zqvpm4gk
  - is-01m0ppz4jkc098qw35es5yd2vq
  - is-01m0ppz44v9tdxhhdhhfyxg7c5
  - is-01m0vdjrk1qr4ezyt84tcvjbkv
  - is-01m0tybgssytxdsdm4xtm6xn8h
  - is-01m0tybh589avf526rvh35kzqj
  - is-01m0tybhfzk2t62dtnbzkhzzyg
  - is-01m0tybhtwqtawke90ae917np4
  - is-01m0vdm7d6j696m0acyqxsq215
  - is-01m0t7n4cdhfrv3fhd7f7vk23f
  - is-01m0vfgc6sh6v7172gbqc9m1e0
  - is-01m0vgje060hee22865m1y22hz
created_at: 2026-08-21T22:08:27.377Z
updated_at: 2026-08-25T03:49:06.181Z
---
Front-to-back performance pass. Measured on this machine, synthetic corpora, Chromium 141.

Browser cold load: 100k files -> FCP 92 ms, first tree row 4,525 ms, 2,550 rows, 28,711 DOM nodes. 1M files (walker truncates at 500,000) -> FCP 176 ms, first tree row 22,328 ms, 25,122 rows, 276,789 DOM nodes.

Waterfall at 100k: /api/tree returns 387,778 B in 38 ms at t+319 ms; /api/events blocks 3,669 ms; /api/catalog returns 4,580,060 B at t+4,733 ms; first row paints at t+4,936 ms. The tree data is in the browser at 319 ms and the client gates on scan completion anyway.

Backend: start-to-serving 771 ms at 9k, 944 ms at 100k, 2,748 ms at 1M (so startup scales with the tree). Walk ~50 us/file. Warm /api/tree 77 ms at 9k, 866 ms at 100k, 4,990 ms and 3.68 MB at 1M. INVENTORY_MAX_FILES = 500_000 truncates silently.

Assets: 432,092 B of vendored JS on every page; blocking the Chart.js stack moves load from 853 ms to 479 ms.
