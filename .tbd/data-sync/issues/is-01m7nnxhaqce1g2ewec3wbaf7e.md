---
type: is
id: is-01m7nnxhaqce1g2ewec3wbaf7e
title: Open anything from the CLI, the skill, and the macOS app (owner asked 2026-11-17)
kind: epic
status: open
priority: 1
version: 40
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/534
    at: 2026-11-20T19:14:56.411Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/539
    at: 2026-11-20T19:14:56.412Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/540
    at: 2026-11-20T19:14:56.412Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/541
    at: 2026-11-20T19:14:56.412Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/558
    at: 2026-11-20T19:14:56.412Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/560
    at: 2026-11-20T19:14:56.412Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/562
    at: 2026-11-20T19:14:56.412Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/571
    at: 2026-11-20T19:14:56.412Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/574
    at: 2026-11-20T19:14:56.412Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/581
    at: 2026-11-20T19:14:56.412Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/582
    at: 2026-11-20T19:14:56.412Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/612
    at: 2026-11-20T19:14:56.412Z
labels:
  - linear
  - Feature
dependencies: []
child_order_hints:
  - is-01m7nnxjg24xah0m43frr8qhrj
  - is-01m7nnxked1k05wen14gte7ccb
  - is-01m7nnxmbvvk8ctg8ckb0tzys7
  - is-01m7nnxnedw2fvq6ef6p0ka73z
  - is-01m7nnxpjnxgxsexg208sjz3qz
  - is-01m7nnxqk729cfx3vnqv22nryh
  - is-01m7nnxrj9txmcjawfmkz6frad
  - is-01m7nnxsky2r2jf9d5n3ac3vty
  - is-01m7nnxtkffq4pxbm414fj6ef5
  - is-01m7nnxvge8wvp33zmj3nkpnvg
  - is-01m7nnxwhgbzv0y2d0811m4fnk
  - is-01m7r8wednnec21h8ac7xbmed6
  - is-01m7raea4zb9dg4bjt8xw1r5ka
  - is-01m7raej2pvscj726pn3nsh2cy
  - is-01m7rd4zsg2sdmwtz7z1w2z9ws
  - is-01m7pvpehjbses9hzggv3ahw4d
  - is-01m7ps02xeyq573ycx69a5zw38
  - is-01m7ps03b12jamq4mztv5v25ec
  - is-01m7ps046phmwqanz6qn7cp44b
  - is-01m7pvqa59443hvcrrczxef78t
  - is-01m7qqfgcrxaw4qrcd855nwf3a
  - is-01m7pme15tmgzne6mwwnr1jykp
  - is-01m7pmegxt7hb25ahy7rv46mg4
  - is-01m7pmefzp0djmrrj0c32x4esr
  - is-01m7pmegespdf49tcxb4pjv4ry
  - is-01m7pr9wa6wb3anxmbsb5cq9rb
  - is-01m7qrt4bdwgj652xr6qw9va4m
  - is-01m7pr9wr8d30pckgvp4teba1z
  - is-01m7nyeb57h28trbdp2m1hy2wk
  - is-01m7nyeamv688pmsbbaq7m85fw
  - is-01m7tdr44212qz0xrah2we67pq
  - is-01m7wya71p80050bqxj40r1y9c
  - is-01m7pk99cegx2xz0sc5wwddsdj
created_at: 2026-11-17T21:16:59.095Z
updated_at: 2026-11-20T19:15:00.592Z
extensions:
  linear:
    id: 5499d118-7011-4615-b052-982dc46ae0f6
    linked_at: 2026-11-20T18:00:06.058Z
---
One invocation, metab TARGET --present, opens any folder, file, or GitHub URL in the native app when installed and preferred, else a browser, and reports what it did. GitHub URLs and File > Open Location in the app, GitHub sign-in checks, and (Phase 2) named UI commands. Owner decisions: the spec's Open Questions.

## Notes

2026-11-20 audit: Open anything from the CLI, the skill and the app: the plan (#534), GitHub links in the app (#539, #560, #607), metab --present (#540, #582), the skill (#562), clone progress and failure states (#571), the status check (#581) and Open Recent (#546) are merged. Open: the follow-ups from #539, #540, #581 and #582, saved tabs and recents (mb-682q), named UI commands (mb-3kr8), and the --present safety decisions (mb-xznn, mb-ex12). The follow-ups of closed mb-87j0 were added.
