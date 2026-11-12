---
type: is
id: is-01m78ftefp9ks9100ebsm7sm29
title: Plugin sources and out-of-process plugin environments
kind: epic
status: open
priority: 1
version: 16
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
child_order_hints:
  - is-01m78fvwszg5ctcvezzfg5tnnp
  - is-01m78fvxctg4g8srm8mr7a06cd
  - is-01m78fvxxksc6ybfthkyzgbtdn
  - is-01m78fvydw6w45j43phwjtsq5w
  - is-01m78fvywxsmc0m4481ypk3zbq
  - is-01m78fvzd8jj1kh0fpm00zt8zk
  - is-01m78fvzzpbj5yemnpk3513vyz
  - is-01m78fw0hdp37ztc29ebfzf2hp
  - is-01m78fw11hmhxr4skq16793f7t
  - is-01m78fw1hhp9r4ft3hze7a8x8j
  - is-01m78fw226k1aejzey9xamd4e7
  - is-01m78fw2nz4rpf95kybngf40zq
  - is-01m78fw36avwntyj23v52vqqdm
  - is-01m78fw3ppt7qjecxb1m4r276q
  - is-01m78fwdh6mt5frdg94thadjkh
created_at: 2026-11-12T18:20:18.805Z
updated_at: 2026-11-12T18:21:23.365Z
---
A system-installed Metabrowser (the metab uv tool and the macOS app) uses new plugins without being reinstalled: registered plugin sources in the configuration home, Python plugins in workers on their own interpreters over a stdlib-only plugin SDK, a caret SDK gate, and the app's plugin settings. Design and phases: docs/project/specs/active/plan-2026-11-12-plugin-sources.md; evidence: docs/project/research/research-2026-11-12-plugin-sources.md.
