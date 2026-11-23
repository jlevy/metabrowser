---
type: is
id: is-01m7wys615s2mfvbc93c9g2pac
title: Branch chooser and ref selection
kind: epic
status: open
priority: 2
version: 16
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/559
    at: 2026-11-20T19:14:51.789Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/577
    at: 2026-11-20T19:14:51.790Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/614
    at: 2026-11-20T19:14:51.790Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/651
    at: 2026-11-20T19:14:51.790Z
labels:
  - linear
  - Feature
dependencies: []
child_order_hints:
  - is-01m7ra9drhbxds0947wdp596ks
  - is-01m7w3mj2y6tpzktkmk8a4ft8k
  - is-01m7vavjge1x571fxtswd8nbng
  - is-01m7r9hj74xgq845rpe64ccp79
  - is-01m7ckmr19etzb7y333astzn64
  - is-01m6wpacpj9wtx02rt1g8kx49m
  - is-01m7td3nq8b0dara7v471jp1rt
  - is-01m7vw9c3htj1h685pjwqgk05k
  - is-01m7r4k134fe1bs8n8z7p8030a
  - is-01m7pf8zxej09pn6zygh242t14
  - is-01m84gfp9fy5szwbh6mwhy8fhq
created_at: 2026-11-20T17:06:34.659Z
updated_at: 2026-11-23T15:30:38.999Z
extensions:
  linear:
    id: e6f489b4-f2f3-4437-9129-fb08702ab54a
    linked_at: 2026-11-20T19:16:46.063Z
---
The Files toolbar's chooser switches a view between branches, tags, commits and pull request heads, in a mirror or beside a checkout's working tree. Landed: the chooser in the toolbar (#577), a local checkout's branch and tag chooser (#559), every ref newest first (#614), scroll kept across refills (#625), and a branch that heads a pull request shown with it (#651).

What remains is the follow-ups from those reviews: switching state after a bfcache restore (mb-0c3a), telling a repository's own pull requests from a fork's (mb-n3hm), redrawing the toolbar around the chooser (mb-k1sx), refused-request windows on other pin switches (mb-ayxi), the Commits landing's HEAD check (mb-8oy4), and the working-tree and branch-snapshot Files workflow (mb-itzy, deferred). Following a branch when the repository moves is the epic mb-2uut.
