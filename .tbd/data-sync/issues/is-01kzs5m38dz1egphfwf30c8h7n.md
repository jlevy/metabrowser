---
type: is
id: is-01kzs5m38dz1egphfwf30c8h7n
title: Repository library and hosted-review roadmap
kind: epic
status: in_progress
priority: 1
version: 81
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
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
  - is-01m2zvdh0wgdt6c9qx38dz52xw
  - is-01m2zvdhtb1gsqjg3azba6mbsr
  - is-01m2zvffb1z2vsseb9d9nqcj6m
  - is-01m35tapm6wjnn235hr3s669b7
  - is-01m35y49h1xhhcn5jgzdy0ne4r
  - is-01m35ypert7n967xft0evk0qwc
  - is-01m3613mjx0zdestpsrpyfpa11
hold: null
hold_until: null
created_at: 2026-08-11T19:43:35.692Z
updated_at: 2026-09-23T02:45:45.306Z
started_at: 2026-09-16T21:10:44.764Z
extensions:
  linear:
    id: 06ad4ed9-e57c-43ff-a0bd-72bc542de8f5
    linked_at: 2026-08-16T08:05:43.412Z
---
Deliver the GitHub-first v0.12 vertical slice on three independent layers: session RepositorySubjects, one shared worktree-free Git object store, and one stable-repository/auth-scoped provider mirror. Open managed URLs and attached user checkouts; serve branches and PR content by full OID without checkouts, indexes, or detached worktrees; define transparent SoftSchema records and trusted plugin registries; use bounded gh api acquisition; cache direct PR bundles before the bounded index; and render shared PR, diff, revision, release, and virtual-navigation views. Local checkouts are never cache authority or mutation targets. Later work retains chooser, issues, GitLab, stacks, and measured large-repository support.

## Notes

2026-09-22 planning-only handoff complete. PR #225 https://github.com/jlevy/metabrowser/pull/225 is at 7a3bd1de04589c38ccc203e79d78a1856ca0a90d, on codex/v012-alpha-test-plan above unchanged #216 b3c001a96eed64eb77961c2b7165b103af98b77c. Fresh CI passed all seven jobs: https://github.com/jlevy/metabrowser/actions/runs/35811262120 . Local make verify passed (3112 pytest tests, two skips; 147 CLI transcripts; audits and installed-distribution checks), final lint and pre-push passed. Working tree is clean; only four planning documents changed.

The user explicitly requested no implementation yet. No runtime code, feature branch, implementation PR, or feature claim was started. Current feature statuses/delegates were preserved. The durable handoff is docs/project/specs/active/plan-2026-09-22-v012-alpha-testing.md#next-prs-and-agent-handoff, linked from TODO.md. Next agent starts with a new foundation-stabilization PR on the live Stack 218 tip, resolves existing findings and review obligations through mb-k900/mb-tsdc/mb-hoae, and records mb-j439 acceptance. Foundation evidence uses current CLI/content routes; acquired HTTP/browser acceptance starts in 2A.

Then publish one new PR per phase: 2A reducers mb-12cz, HTTPS mb-s1lt and URL/serving mb-ew38 -> mb-innz; 2B jobs mb-jlon and convergence mb-bgn8 -> mb-bf94; 2C selection mb-2xq7 -> mb-9aku on the exact green 2B head. HTTPS gates 2A publication. Parent mb-bi2c retains SSH and gates final mb-n2ro landing without blocking the first HTTPS test milestone. No tbd release or cleanup is a prerequisite. Astra checked scope/dependency boundaries and Sol checked live stack, links, statuses and dependency ordering. Keep the whole stack for stabilization and explicit landing approval; no merge or release occurred.

Earlier status history:
2026-09-22 final follow-up: PR #225 is updated to ef334432dde5449d29a7f097a8dc2084fdb08f20 over unchanged #216 b3c001a96eed64eb77961c2b7165b103af98b77c. All eight Stack 218 PRs are OPEN, non-draft, contiguous, MERGEABLE/CLEAN, with seven successful checks each. Current main 6c278f3f is an ancestor of the integration tip. Fresh CI: https://github.com/jlevy/metabrowser/actions/runs/35808364944 . Final evidence and walkthrough: https://github.com/jlevy/metabrowser/pull/225#issuecomment-5787687825 . Full review ledger: https://github.com/jlevy/metabrowser/pull/216#issuecomment-5786877244 .

The expanded feature map distinguishes built, partial and planned scope and later work, with T0 available now, the first default-branch URL browser checkpoint after 2A, full T1 after selected-ref/branch integration, direct PR T2 and discovery/navigation/anchors T3. The explicit Phase 2B background worker is mb-bgn8; M10b covers provider rebind. Local make verify and the pre-push gate passed (3112 pytest tests, two skips; 147 CLI transcript checks; audits and installed-wheel/distribution checks). The real CLI cold/warm/origin-absent T0 smoke passed; fixture-server startup/HTTP was checked, without claiming full manual visual acceptance or GitHub URL/PR E2E support. Astra checked feature/design boundaries and Sol verified fresh CI, ancestry, mergeability and documentation consistency.

No tbd release, upgrade or shortcut cleanup is a prerequisite for product implementation, testing, landing or release. mb-dbue/#219 are independent optional maintenance. This supersedes historical notes mentioning an upstream tbd release wait. Product acceptance findings including mb-sumg remain open; mb-gnr9 owns future installed/browser acceptance. Future work extends this same stack, and whole-stack landing awaits product stabilization and explicit user approval. No merge or release was performed.

Earlier history (superseded where noted):
2026-09-22 follow-up: no work is held on tbd. All eight current stack PRs are ready for review; #217/#216 draft flags were removed at the user’s request after live ancestry, mergeability and green-CI checks. This changes mechanical mergeability, not feature completion or landing authorization. The expanded alpha plan on #225 maps all repository/GitHub features to built, partial or planned, lists deferred scope, and supplies a testing walkthrough from local browser/Git foundation through default URL smoke, selected branches, direct PRs and discovery/anchors. Optional shortcut cleanup mb-dbue has no upstream-release dependency and is not a product gate.

Earlier history:
2026-09-22 current status: v0.12 implementation remains on formal GitHub Stack 218: #125 design -> #134 Phase 0 records -> #136 installed contracts -> #139 source binding -> #140 cache format -> #217 file:// acquisition (draft) -> #216 consolidated source boundary and immutable Git pin (draft). Current integration head b3c001a96eed64eb77961c2b7165b103af98b77c includes main 6c278f3f and the merged #209 HTML trust foundation through #224. No stack PR has landed. Current runtime supports file:// acquisition, pinned --show and --api; GitHub URL reduction/HTTP serving, HTTPS/SSH acquisition, provider runtime and PR views remain planned. The alpha test plan at docs/project/specs/active/plan-2026-09-22-v012-alpha-testing.md defines T0 local foundation, T1 repository URL alpha, T2 direct PR alpha, and T3 full v0.12 discovery/navigation/anchors. mb-gnr9 owns installed-artifact and real-browser alpha acceptance. Future implementation/testing/stabilization PRs extend the current stack tip; hold the entire stack until stabilization and explicit approval through mb-n2ro. mb-eegt owns this review/status reconciliation. Full review: https://github.com/jlevy/metabrowser/pull/216#issuecomment-5786877244 . #219 remains separate process maintenance awaiting a get-tbd release containing upstream #316; #87/#51 are separate research PRs. Historical handoff follows.

2026-09-19 handoff: formal GitHub stack #218 (nothing on main):

#125 design → #134 Phase 0 format (folded #130 #132 #133) → #136 Phase 0C (folded #135) → #139 Phase 0D (folded #138) → #140 Phase 1A → #217 Phase 1B-a draft (folded #208 #210) → #216 Phase 1B source+pin draft (folded #156 and #211–#215).

Independent of the cache stack: HTML #209 (draft, on main), PR-sizing overlay #219, dependabot #207, research #87 and #51.

Superseded crumb PRs are closed. Landing is mb-n2ro only, after explicit approval.

Spec status refreshed on #216 (repo library + hosted review) and #209 (HTML).

2026-09-22 completed review/publication: https://github.com/jlevy/metabrowser/pull/225 is the ready-for-review eighth layer of Stack 218, head ff94e3676bf0f7caab7a8bdfdbb18eb8b1f8e1c9 over #216 b3c001a96eed64eb77961c2b7165b103af98b77c. The original seven heads and exact chain are unchanged. All seven CI checks passed: https://github.com/jlevy/metabrowser/actions/runs/35803858717 . Local make verify passed (3112 pytest tests, two skips, 147 CLI transcript checks, dependency audits and installed-wheel/distribution checks); pre-push gate passed. Real unmodified Git 2.50.1 CLI T0 smoke passed for cold/warm acquisition, nested Markdown/JSON/tree/progress, origin-absent reuse, and local filesystem inspection. Independent Astra plan review found no actionable plan blocker: https://github.com/jlevy/metabrowser/pull/225#issuecomment-5787107670 . Full top-level review: https://github.com/jlevy/metabrowser/pull/216#issuecomment-5786877244 . #136/#139 later functional deltas received independent technical review; #217/#216 acceptance remains open. New finding mb-sumg and future installed/browser acceptance mb-gnr9 remain open. Specs, QA procedure, roadmap, active release labels, PR descriptions and dependency graph are reconciled. mb-xada historical handoff is closed; #219/mb-dbue remain open awaiting a released tbd replacement. All future work extends Stack 218 and the whole stack stays held for stabilization and explicit landing approval. No GitHub URL/PR end-to-end pass, merge or release is claimed.
