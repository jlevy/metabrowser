---
type: is
id: is-01kzs5m38dz1egphfwf30c8h7n
title: Repository library and hosted-review roadmap
kind: epic
status: in_progress
priority: 1
version: 69
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m0b71xgqp0jgz007h0wtzr3z
  - type: blocks
    target: is-01m0c1by1cmexbqhx6xeb3b10p
  - type: blocks
    target: is-01m0c4dfbfnqg3q53y7xzbgc0a
child_order_hints:
  - is-01m10wbv02twkf4z2t3szd5835
  - is-01m10vgc38hk6pm0rkgzw2hsk0
  - is-01kzsb4jzq5a37evdz4bk0dqg4
  - is-01kzsb4jnyd56wy89xmztkmz2m
  - is-01kzsb4k9hwrt25jj9j6svkvaf
  - is-01m10vgv018nef5svd0kb54gv9
  - is-01m10vgvh4pvre1adnkgm2egp1
  - is-01m10vgw6vhq82cd495kvhh9gf
  - is-01m10xd666fefs5z7ft5m58zj0
  - is-01m10vgwqwn8gjdv8fm183vztr
  - is-01m10xd6s2fy7qthahs3cz25gk
  - is-01kzt6hdasbhx6maqzvtxntxj7
  - is-01m11xe1pr09sc61h58tq0rcwd
  - is-01m1389aetecehg10qdf7zb9rz
  - is-01m1389bszmmkqj7d90sq8p3bj
  - is-01m1389rewn2mkj8emj3wxwpr7
  - is-01m2h3qzqep911zn6jwx7dmb9t
  - is-01m2h3vkgbkeq82ch4mzkrch1g
  - is-01m2h3wteafc7mt3x0efnv4xex
  - is-01m2h5ar8jct8wbp94xj39gkq4
  - is-01m0dkj0gqvpzpxm7t1tpshf30
  - is-01kxry31k2e62styhj8t59jj12
  - is-01m2h7gjc36fqv8cv38qd9zynr
  - is-01m2h7jjga1ge5dzvs913n5fgs
  - is-01m2h9jhhdn774nzxs9j94h726
  - is-01m2h9jn8eq1896pa2567wcw9s
  - is-01m2ktnhjgw0bsgcaw6e8h9x2e
  - is-01m2kw2b66x74xxjjtdp3wrsr4
  - is-01m2kw2bht6rte4gtjdq39n1yt
  - is-01m2k713pxra1ns2fk3pcwrpb6
  - is-01m2kwk6h6pzxanejy6c339r08
  - is-01m2nz79vrjb2vpp5ydxra84e5
  - is-01m2nz8q666pwqcbxbn7d5jr6x
  - is-01m2nz9gwd4wyxmrpx49cp9yck
  - is-01m2nzb0geg0hkaapyvj0hdb49
  - is-01m2p1prnv5sdvx5atj08ckqn2
  - is-01m2p1ps48qjh1qt3wmk8s63ra
  - is-01m2p1pshr699c6pf8xqeer16j
  - is-01m2p1pszq015wyj1b3admbt8r
  - is-01m2p38vk3d6gkv2ts21bzfzw3
  - is-01m2pn3sm2980e2bjnfd3b4xvp
  - is-01m2pttd3exe4x0cjsvyssr21k
  - is-01m2xb08ytynaae0w368awg1s2
  - is-01m2wbxg2pb42nj7zacndrsvsc
  - is-01m2ynskxv64d74tpy85555mef
  - is-01m2ynsqxttgb6w2tyev2vcvb1
  - is-01m2yp1cgtgy3arg3nvfd54sck
  - is-01m2yxd3tnr1s2zf0h0jat1ey2
hold: null
hold_until: null
created_at: 2026-08-11T19:43:35.692Z
updated_at: 2026-09-20T08:02:30.356Z
started_at: 2026-09-16T21:10:44.764Z
extensions:
  linear:
    id: 06ad4ed9-e57c-43ff-a0bd-72bc542de8f5
    linked_at: 2026-08-16T08:05:43.412Z
---
Deliver the GitHub-first v0.11 vertical slice on three independent layers: session RepositorySubjects, one shared worktree-free Git object store, and one stable-repository/auth-scoped provider mirror. Open managed URLs and attached user checkouts; serve branches and PR content by full OID without checkouts, indexes, or detached worktrees; define transparent SoftSchema records and trusted plugin registries; use bounded gh api acquisition; cache direct PR bundles before the bounded index; and render shared PR, diff, revision, release, and virtual-navigation views. Local checkouts are never cache authority or mutation targets. Later work retains chooser, issues, GitLab, stacks, and measured large-repository support.

## Notes

2026-09-19 handoff: formal GitHub stack #218 (nothing on main):

#125 design → #134 Phase 0 format (folded #130 #132 #133) → #136 Phase 0C (folded #135) → #139 Phase 0D (folded #138) → #140 Phase 1A → #217 Phase 1B-a draft (folded #208 #210) → #216 Phase 1B source+pin draft (folded #156 and #211–#215).

Independent of the cache stack: HTML #209 (draft, on main), PR-sizing overlay #219, dependabot #207, research #87 and #51.

Superseded crumb PRs are closed. Landing is mb-n2ro only, after explicit approval.

Spec status refreshed on #216 (repo library + hosted review) and #209 (HTML).
