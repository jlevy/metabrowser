---
type: is
id: is-01m82yzrw40w07dnw6zhsg8jep
title: "Treemap: deeper nesting, containment fix, compact map on Overview"
kind: feature
status: in_progress
priority: 2
version: 26
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/722
    at: 2026-11-23T02:52:15.430Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/723
    at: 2026-11-23T02:52:15.907Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/724
    at: 2026-11-23T02:52:16.428Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/752
    at: 2026-11-23T11:16:31.892Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/754
    at: 2026-11-23T14:37:22.831Z
delegate: claude-code@spud10
labels: []
dependencies: []
child_order_hints:
  - is-01m832rs4ryhw09n31ah5haztf
  - is-01m832rz5kkqdjm64fftcyjsb7
  - is-01m832s53eb7m4chdhzwncqt3r
  - is-01m836hpsa4m1zk5z2ddmrkd0e
  - is-01m836hyx390ja57mj4t10yyat
  - is-01m836j7a322nctgrb6c3nftm3
  - is-01m836qya23kghgk2m3t9em8nc
  - is-01m836r7jghtaq3hc7q5cny9sw
  - is-01m836s55277yzehg502zen0ra
  - is-01m83h8w9k2704ftceq2v3nspz
  - is-01m83h8y2j1v6y2wxa2haeq125
  - is-01m83r0j5x920yvdc3hrnevzvy
  - is-01m8446sw5r7q5krepma7rn6k4
  - is-01m8449c4qqskq8z3p7dq8dw6n
  - is-01m849sm0qja52cpa08ea7p6r9
  - is-01m84fe4rh1066zbwm7s640p9m
hold: null
hold_until: null
created_at: 2026-11-23T01:05:37.128Z
updated_at: 2026-11-23T15:12:19.725Z
started_at: 2026-11-23T01:05:57.669Z
closed_at: null
close_reason: null
resolution: null
duplicate_of: null
---
The Treemap drew two levels, laid out to the viewport's border box so right and bottom edge cells were clipped, and the rollup's breadth-first node budget left large folders unexpanded. Nest as deep as cells have room (framed nesting for small folders), spread the cell budget by area, request the rollup's max depth and width with heaviest-first emission, fix the drawable box, and extract the map into a component also drawn compactly under File Overview.
