---
type: is
id: is-01m7wys3bp2ndx4v4m26exf0hz
title: File ages, recency, and Files-tab grouping
kind: epic
status: open
priority: 2
version: 20
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/546
    at: 2026-11-20T19:14:57.944Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/572
    at: 2026-11-20T19:14:57.946Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/601
    at: 2026-11-20T19:14:57.946Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/643
    at: 2026-11-20T19:14:57.946Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/652
    at: 2026-11-20T19:14:57.946Z
labels:
  - linear
  - Feature
dependencies: []
child_order_hints:
  - is-01m7w8mt96mxaz0py8ke8acx3n
  - is-01kxnxdp06yjcb57d62y03kv1m
  - is-01m7nb50wb8thbyrmhdh8yxnqx
  - is-01m7k6w6hj2p10bfr9zkd20c4x
  - is-01m7tecv9rdnckqeaddnye7b54
  - is-01m7jkb4mgqczq02t9x6y5czy7
  - is-01m7jfjnq50yzgkyde2n28krmy
  - is-01m7jfjn3jmmg4ax4kr29abqpg
  - is-01m7hh0sdnmyfxjrqzgkj1zn9x
  - is-01m7s898skvvqr3pjh0h263x1q
  - is-01kzn46nh5ezzj2re7rcc0gx8n
  - is-01m7vrv37xz32vhmy3h0zdjamh
  - is-01m7r804jrhk61bnjr979m4q94
  - is-01m7s7apxe55ek1pds3fa2475v
  - is-01m7p8c8jxvvb9qgs08wea9nk3
created_at: 2026-11-20T17:06:31.923Z
updated_at: 2026-11-20T19:16:45.070Z
extensions:
  linear:
    id: 1e4ba3ec-be2e-4e6a-87f7-f71f8406875c
    linked_at: 2026-11-20T19:16:45.065Z
---
The Files tab groups, filters and dates what it lists: Group by (By age, By file type), Modified within, Recent, and each entry's age. On a folder the ages come from the inventory; on a Git revision they come from each file's last commit (git last-modified), which landed in #643 and #652.

What remains: a submodule entry is in no age group (mb-e3mn); directories in Recent results (mb-f42e); a folder header's age label that changes width moves its neighbours (mb-v4u6); filter-menu counts and a hidden file's note while tallies are unknown (mb-v2ls, mb-nutq); row positions and queued passes in the tree (mb-jdk0, mb-l2xc); the Group by session's failure mode and first-click case (mb-2fgr, mb-4d7s); one filter count (mb-zo3t); and the file-tree spacing (mb-8xcu, deferred). A cacheable recency filter belongs to mb-48vd.
