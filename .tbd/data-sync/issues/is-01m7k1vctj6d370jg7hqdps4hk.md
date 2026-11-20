---
type: is
id: is-01m7k1vctj6d370jg7hqdps4hk
title: Design the macOS app's publishing setup (signing, notarization, DMG, install checks) to a current best-practice standard, adapting a sibling Electron app's proven setup
kind: task
status: closed
priority: 1
version: 50
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/509
    at: 2026-11-20T17:05:37.698Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/510
    at: 2026-11-20T17:05:37.702Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
child_order_hints:
  - is-01m7k2w8wrwrypxm2vxyqaaa8v
  - is-01m7k2wy21hnkyp3p2sssrjfty
  - is-01m7k2wyj6vv09snsk781hpvsz
  - is-01m7k2wz25n92m141a2c6rzj3m
  - is-01m7k2wzxnnfkzcr7eg8ngptcq
  - is-01m7k2x14rvw39nm958bfcwv67
  - is-01m7k2xcrjxtgfe2mepxas1434
  - is-01m7k2xdgr9b8sra4vrd372fe2
  - is-01m7k2xe5286604ke24q8svdgq
  - is-01m7k5kan8b6ajd0jjz4gey7d0
  - is-01m7k5kb9na8d335et9yw8ptpz
  - is-01m7k5kbx9eb3ezaef642z3y8t
  - is-01m7k5kcdk2843pngd9b1e1aw6
  - is-01m7k5kcwsddyvtn6hazwkkhvs
  - is-01m7k5kdfab9ns5rn21szrvcbj
  - is-01m7k5kdz3wgsej7y3wwmj4rnn
  - is-01m7k5kehjqg1bkt67wa3xbwq4
  - is-01m7k5kf0rmrxa29s51s9csa42
  - is-01m7k5kfgwtr16yhe2w1cjyj1x
  - is-01m7k5kg6q778zm928djg5dy0m
  - is-01m7k5kgqh9xm6hnsdbh2p3fz7
  - is-01m7k5kh8snytzh1w7sgg90j4b
  - is-01m7k5khwc6zbd47z3rgabr277
  - is-01m7k5kjf3pyy8hyf0jcv29dgq
  - is-01m7k5kjzg1741f2bc2t2107ya
  - is-01m7k5kkfgb40z07d073xz0yy1
  - is-01m7k5kkz0yn634070xpqt077q
  - is-01m7k5kmf28554d1h1qpzxwvmz
  - is-01m7k5kmyz7kxbsde9nv0xx76c
  - is-01m7k5knhyp4wsz8fy1ndc2dj5
  - is-01m7k5kp1wncwvg8b38azrep0b
  - is-01m7k5rv09cpqqjzfdt2vk4qdp
  - is-01m7k5rvkfvf6ps5pn7g5d6rt0
  - is-01m7kbqszvgyye5ezs0pyj29c6
  - is-01m7kbqtzzz06w5hqa39vmapkz
  - is-01m7kbqvvr4qsp7bzpxf4dqqg9
  - is-01m7kbqwq8411xmx3k8kx0bghm
  - is-01m7kbqxknjwbz2n4prbk2gz0s
  - is-01m7kbqyr1865jc7p0c92vapjx
  - is-01m7kbqzkj0f323836h485k0m5
  - is-01m7kbr0fe467vajdbw6njqb71
  - is-01m7kbr1b46wpcycte58vqjx3y
hold: null
hold_until: null
created_at: 2026-11-16T20:47:48.560Z
updated_at: 2026-11-20T19:15:59.332Z
started_at: 2026-11-16T20:49:22.082Z
closed_at: 2026-11-17T00:47:22.328Z
close_reason: "Publishing plan landed in #485 (squash); implementation beads under it remain"
resolution: null
duplicate_of: null
extensions: {}
---
Owner, 2026-11-16: look at the developer setup of a sibling private Electron app and its GitHub repo, design what metabrowser's Apple app publishing needs to be equivalent, including its testing tools that check app signing and that the app downloads and sets up correctly; adapt what makes sense, follow current best practices, and bring them up to date (that repo is over a year old). The sibling repo is private: metabrowser's public docs describe adopted practices without naming it or copying from it. Deliverable: a plan spec PR.
