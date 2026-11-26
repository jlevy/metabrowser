---
type: is
id: is-01m7wysdnvzch4gb5zvqwvn04e
title: "Markdown and structured-text rendering: front matter, diagrams, untrusted content"
kind: epic
status: in_progress
priority: 2
version: 47
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/511
    at: 2026-11-20T19:14:52.926Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/527
    at: 2026-11-20T19:14:52.927Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/542
    at: 2026-11-20T19:14:52.927Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/597
    at: 2026-11-20T19:14:52.927Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/616
    at: 2026-11-20T19:14:52.927Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/622
    at: 2026-11-20T19:14:52.927Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/626
    at: 2026-11-20T19:14:52.927Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/644
    at: 2026-11-20T19:14:52.927Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/874
    at: 2026-11-26T07:52:54.894Z
labels:
  - linear
  - Feature
dependencies: []
child_order_hints:
  - is-01m7wyspfffhwcfcze4mke8jjp
  - is-01m7tb5hr58w6wt67a59yaqgjr
  - is-01m7sawbes549q5f7yaanz215e
  - is-01m7vcqgjwkr50hfknj74hvddz
  - is-01m7p1hjrfddg8p7vhepbvf3pm
  - is-01m7r95tjdh9t60p9kze2wm2wm
  - is-01m7r95zvyws55krqqyrbraetk
  - is-01m2eb9qf306kf33dg8kvr0wzd
  - is-01m2f38npt37vtbyys1t8bgp7s
  - is-01m2f38n8mztavm6vactpfxn04
  - is-01m7vcpx28mh521jshz156f9e5
  - is-01m7ewf5qa5hmke5tbwa5skgd3
  - is-01m6f51bschh98hn3w6r9pdenw
  - is-01m7p2h95esb1eyz0wj18fs2rb
  - is-01m6yts0bscnpa5patn8wh4dm4
  - is-01m7tww736dq91cgkqdr3hec3e
  - is-01m7p2h9n62dqsw4kcbcwba0qr
  - is-01m7p2ha44m07vhtqayk6gphgj
  - is-01m7vabmvnertkaeg2cs401pq6
  - is-01m7pbn9rb92d2jc67f8rycy5h
  - is-01m7f5ex295gdhxggbr3nsywcd
  - is-01m7jer89rhnswzbq9dbrzkafv
  - is-01m7pbmj503na98d3a3a4jqc3b
  - is-01m7pbmjraba81fxxr4j11wa7r
  - is-01m7p7s75fpxmkw7z647aaqap2
  - is-01m7pbmk965r11qkqa2af36b25
  - is-01kzz211w19g9y39ct7qf0hy1z
  - is-01m0k3nbmdvy9x8g3r8t9ckzjt
  - is-01m7nz91me6818xtzmqzt9zrhs
  - is-01m7x1emmz9p122tphtdxdqp4e
  - is-01m7vrbj7pcmfdv8tabbb57wpe
  - is-01m7v62n9f3y3qh0qxe9m6ap2y
  - is-01m7tnaxethq70h5dxyhfdzz8r
  - is-01m8bat4973h1bjzvpkwd8qjdy
  - is-01m8be2m0hdtw8yj4x0f6rrbs7
  - is-01m8be2msec8pk98cjcrb5wqzv
  - is-01m8be2nhqt2rt2xa90vkcr2qv
  - is-01m8be2p7e9ewzpbprqy5107sy
  - is-01m8cte9rj7s82c4ywp7n3ph3z
  - is-01m8cwdyzkmr5se3amyrmb5tc2
created_at: 2026-11-20T17:06:42.489Z
updated_at: 2026-11-26T21:33:20.755Z
extensions:
  linear:
    id: c23452d1-8d76-491e-86d9-3278c87bdb31
    linked_at: 2026-11-20T19:16:51.773Z
---
Rendered Markdown (KPress), wiki links and transclusion, front matter, the structured YAML and JSON views, and Mermaid diagrams, in the trusted and the inert (untrusted) profiles. Landed: Mermaid in Markdown (#597) and in pull request text (#616), GitHub's layout attributes (#626), bounded front matter parsed off the event loop (#542), untrusted Markdown rendered in an inert child under a deadline (#527), and the remote-image policy (#644).

What remains: Mermaid waits on the owner testing and merging kpress#80, then the repin (mb-tbq9, mb-d515); inert documents' diagram layout (mb-htyq); YAML alias bounds in the structured viewer (mb-7th1) and its other defects (mb-hs06, mb-59mp); Markdown bounds, robustness and wiki follow-ups (mb-k8os, mb-k0s0, mb-fvs1, mb-286z, mb-cz9v, mb-m4u9); TOC and transclusion polish (mb-hpoq, mb-jt6l, mb-9q0a, mb-2nqa, mb-4el3); KPress follow-ups (mb-no22, mb-jue2, mb-gc3c, mb-4cwy); and the front matter follow-ups from #542 (mb-2y6a, mb-ah1x, mb-s8bo, mb-993s). Nested: the inert-render hardening from #527 and the Markdown navigation evaluation (mb-fbm2).
