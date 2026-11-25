---
type: is
id: is-01m82yzrw40w07dnw6zhsg8jep
title: "Treemap: deeper nesting, containment fix, compact map on Overview"
kind: epic
status: open
priority: 2
version: 50
spec_path: docs/project/specs/active/plan-2026-11-22-treemap-canvas-granularity.md
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
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/757
    at: 2026-11-23T16:09:40.152Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/763
    at: 2026-11-23T17:32:32.217Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/764
    at: 2026-11-23T20:35:15.807Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/767
    at: 2026-11-25T02:25:08.613Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/769
    at: 2026-11-25T02:25:08.739Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/772
    at: 2026-11-25T02:25:08.739Z
delegate: claude-code@spud10
labels:
  - linear
  - Feature
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
  - is-01m84fn84fkd775g8v1n781jzw
  - is-01m84fn94wz47am8cwywj3angp
  - is-01m84fn9xvp53f535cfk3qd9cy
  - is-01m84frddm4hytc6q59eqptsbn
  - is-01m84s4gv2cynykbv302f8ykn4
  - is-01m8501z5hf5rvhsst744a0beq
  - is-01m850221xfhrw4wq07prpwv8r
  - is-01m85023kajww4yrn32509jw3b
  - is-01m85024vhka9sywam81k0jdgx
  - is-01m850274x9skfp0jgxdqh6vht
  - is-01m85686ah5d88qhkbbp5bnt89
  - is-01m857vmkheywjpjekanh9sha6
  - is-01m857zm4f90nmkhmzc6sc9tym
  - is-01m85azcjx7bnsywxddhmbw2w6
  - is-01m85c06r26g2944esxtff8hsg
  - is-01m85f546ddhc098egv5e0ehqg
  - is-01m85f5etwt3saw23vzckem891
hold: null
hold_until: null
created_at: 2026-11-23T01:05:37.128Z
updated_at: 2026-11-25T03:55:51.631Z
started_at: 2026-11-23T01:05:57.669Z
closed_at: null
close_reason: null
resolution: null
duplicate_of: null
extensions:
  linear:
    id: a1f2ad9a-4950-49f4-a746-607f45b67213
    linked_at: 2026-11-25T03:55:51.631Z
---
The Treemap drew two levels, laid out to the viewport's border box so right and bottom edge cells were clipped, and the rollup's breadth-first node budget left large folders unexpanded. Nest as deep as cells have room (framed nesting for small folders), spread the cell budget by area, request the rollup's max depth and width with heaviest-first emission, fix the drawable box, and extract the map into a component also drawn compactly under File Overview.
