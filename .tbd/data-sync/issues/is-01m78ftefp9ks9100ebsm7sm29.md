---
type: is
id: is-01m78ftefp9ks9100ebsm7sm29
title: Plugin sources, process isolation, and out-of-process plugin environments
kind: epic
status: in_progress
priority: 1
version: 35
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/380
    at: 2026-11-25T02:23:25.076Z
labels:
  - linear
  - Feature
dependencies: []
child_order_hints:
  - is-01m78fvwszg5ctcvezzfg5tnnp
  - is-01m8bfwyrthng58j0rn5mjw2q5
  - is-01m8bfwz44tckg3hn0sh1r7nfr
  - is-01m8bfwzfe1q07kf87x8h1xnx9
  - is-01m78fvxctg4g8srm8mr7a06cd
  - is-01m8bfx06xz0wsd6rvtr586jbg
  - is-01m78fw1hhp9r4ft3hze7a8x8j
  - is-01m78fvydw6w45j43phwjtsq5w
  - is-01m8bfwztw84vfapjmyap7ta72
  - is-01m78fvywxsmc0m4481ypk3zbq
  - is-01m8bfx0ydnsv7hpxbm60fxhzj
  - is-01m78fvxxksc6ybfthkyzgbtdn
  - is-01m78fw226k1aejzey9xamd4e7
  - is-01m78fvzd8jj1kh0fpm00zt8zk
  - is-01m8bfx0jk64cgj3sz7sm2nav4
  - is-01m78fvzzpbj5yemnpk3513vyz
  - is-01m78fw0hdp37ztc29ebfzf2hp
  - is-01m8bfx1q8z65g0qyts31p4j6t
  - is-01m78fw3ppt7qjecxb1m4r276q
  - is-01m8bfx1aaxf7qyzn1n2h1ap4v
  - is-01m78gmwnk00rz776w8w8k7g9j
  - is-01m8bfx231spr2pvhzetq1j5as
  - is-01m78fw2nz4rpf95kybngf40zq
  - is-01m78fwdh6mt5frdg94thadjkh
  - is-01m78fw11hmhxr4skq16793f7t
  - is-01m78fw36avwntyj23v52vqqdm
created_at: 2026-11-12T18:20:18.805Z
updated_at: 2026-11-26T08:36:54.664Z
extensions:
  linear:
    id: 2c899caa-16c3-454c-acd8-d66b8a42baf7
    linked_at: 2026-11-20T19:16:39.797Z
---
A system-installed Metabrowser (the metab uv tool and the macOS app) uses new plugins without being reinstalled, and picks up a repository's checked-in and library-shipped plugins after one consent per clone. Plugin Python runs in workers on its own environment's interpreter, with a runtime package the host ships (metabrowser_sdk); every child process goes through one core isolation facility extracted from the PDF preview's sandbox and the SQLite readers, which separates a process that is only separate from one the operating system confines; a repository's plugins run confined by default; one registry with scoped sources lives in the state home, read fail-closed; a clone is identified by a token and a decision binds its environment and providers; one plugin API version under a caret gate; one executable. Design, eleven Key Decisions awaiting the owner, and phases: docs/project/specs/active/plan-2026-11-12-plugin-sources.md; evidence: docs/project/research/research-2026-11-12-plugin-sources.md; spikes and probes: explorations/plugin-worker-spike/.

## Notes

2026-11-26: second revision of the design in draft PR #380, after a review against main. Adds the isolation layer and Key Decision 11, fixes the trust bindings, drops the second executable, renames the runtime, reorders the phases, and defers managed packages (mb-8ii8). Ten beads added: mb-e7t8, mb-v2m7, mb-gmut, mb-nes2, mb-x1j5, mb-i6i6, mb-sbjf, mb-p62c, mb-5qw0, mb-qoh1. The key decisions still await the owner; the beads are open. 2026-11-20 audit: The design is in draft PR #380 and its key decisions await the owner; the beads are open.
