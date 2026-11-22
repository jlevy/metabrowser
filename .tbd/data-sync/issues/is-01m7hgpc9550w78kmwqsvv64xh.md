---
type: is
id: is-01m7hgpc9550w78kmwqsvv64xh
title: "Release 0.13: prepare the PyPI package and macOS app release (owner asked 2026-11-15)"
kind: epic
status: open
priority: 1
version: 48
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/485
    at: 2026-11-20T19:14:59.103Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/509
    at: 2026-11-20T19:14:59.103Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/510
    at: 2026-11-20T19:14:59.103Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/556
    at: 2026-11-20T19:14:59.103Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/686
    at: 2026-11-21T20:49:44.905Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/687
    at: 2026-11-21T20:49:44.906Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/688
    at: 2026-11-21T20:49:44.906Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/689
    at: 2026-11-21T20:49:44.906Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/690
    at: 2026-11-21T21:14:54.528Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/691
    at: 2026-11-22T19:38:11.346Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/692
    at: 2026-11-22T19:44:26.095Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/694
    at: 2026-11-22T19:57:13.963Z
labels:
  - linear
  - Improvement
dependencies: []
child_order_hints:
  - is-01m7hhr1qbg4f07e1scdq20d7n
  - is-01m7hhr29ft7vypdg5eaz0md2s
  - is-01m7hhr2r1bmm0ve8a6qs5nnqw
  - is-01m7hhr36mmrjwfw662gmgngf6
  - is-01m7hhr3n6wpvfm1zpsxjh210t
  - is-01m7hhr43k5rc7ytbxg1vx031s
  - is-01m7k1vctj6d370jg7hqdps4hk
  - is-01m7k3fdgyayshmca073e9p811
  - is-01m7kaq8nw86eh3g3rkfr327ht
  - is-01m7kf0t56psry2ybyejpna2b4
  - is-01m7k2wzxnnfkzcr7eg8ngptcq
  - is-01m7k2x14rvw39nm958bfcwv67
  - is-01m7k2xdgr9b8sra4vrd372fe2
  - is-01m7k2xe5286604ke24q8svdgq
  - is-01m7k5rvkfvf6ps5pn7g5d6rt0
  - is-01m7p85rbgvd5kha2bqqk8026r
  - is-01m7jk552r4jya1wfe0p9acfmn
  - is-01m2670kk25nq2q162rbd2nqc7
  - is-01m7zxah5jgvwfbskqf0e5s3v3
  - is-01m7zxakx0t9ec4qjqr0jt0f1s
  - is-01m7zxaqehf7tth92g7q9b68x6
  - is-01m7zxdtskkg2jp93rhm2w04xg
  - is-01m7zxdvff7m5tfqva07bvjt4b
  - is-01m7zxdw58ddpyp4y5w55tr3pm
  - is-01m7zxyjbk1fbkqxkc03de40wk
  - is-01m7zxyjvts8tm1hhm8s7ny9kr
  - is-01m82aqg2b9ak3ar74zgrns43m
  - is-01m82b5p8rvtkhw21tr4egkqqb
  - is-01m82c87wf2gwme1js33t2t59y
  - is-01m82c891g8pvraawchx4pwgvh
  - is-01m82c8abm03xzpvctgea74ywj
  - is-01m82c8bd5hw5cyz98wty5qm63
  - is-01m82ckpd2h34zw1tqdv7cqedx
  - is-01m82cqd1k63a3964mfpsa8da6
created_at: 2026-11-16T06:28:43.940Z
updated_at: 2026-11-22T19:57:13.976Z
extensions:
  linear:
    id: a18aa3cd-0329-4c1c-bca3-17921fe6703e
    linked_at: 2026-11-20T17:59:10.803Z
---
Owner: "and go through the thoroough process to prepare a release of macos and metabrowser app". Follow docs/publishing.md and apps/macos/README.md: land stacks #446 and #454, make verify, previous-release performance comparison, release-prep record, version, notes, owner approval of exact commit and notes, then publish.

## Notes

Plan: attic/coord/release-plan-0.13.md in the coordinator worktree. Owner decisions 2026-11-16: package 0.13.0 and app 0.1.0 (raise the app's floor to 0.13.0 after the v0.13.0 tag); ship the app as an alpha despite the WebKit gate (mb-gvtw), listing the limitation; #453 is fixed and landed with the docs stack; the 0.12 follow-ups (mb-m20f, mb-etqi, mb-2g6f) do not gate 0.13 and are recorded as deferred. Blockers needing the owner: disk (5.9 GiB free; need about 25 GB), Low Power Mode on, Developer ID identity present but not valid (G2 intermediate missing), no notary profile.

2026-11-17 handoff: Release status 2026-11-17: all UI PRs merging; owner-only before signing: install Developer ID G2 intermediate, create App Store Connect team API key, dedicated release keychain with -x import (offline .p12 kept), store metabrowser-notary profile, turn on immutable releases (plan-2026-11-16-macos-app-publishing O1-O9). Agent steps remain: make verify at candidate, perf comparison, release-prep PR (CHANGELOG 0.13.0, QA record), owner approval, publish v0.13.0, app floor 0.13.0 PR, WebKit rerun, signed DMG macos-v0.1.0.

2026-11-20 audit: Release 0.13 preparation: the owner's chores (mb-0msg, mb-21t6), the candidate gates (mb-brvm, mb-icss, mb-b246, mb-1d8p), and the macOS release workflow and signing CI tasks (mb-3ey5, mb-eoez, mb-mww5, mb-yqrs, mb-epgm), now direct children. Added: mb-wfyt and mb-8f19 (rebuild and reinstall the dev app from main) and mb-9uyb (separate artifact construction from OIDC publishing).
