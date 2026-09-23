---
type: is
id: is-01m2kw2b66x74xxjjtdp3wrsr4
title: "GitHub Phase 2A review: publish repository URL-open PR"
kind: task
status: open
priority: 1
version: 16
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: null
labels:
  - stack:publication
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2kw2bht6rte4gtjdq39n1yt
  - type: blocks
    target: is-01m2h7gjc36fqv8cv38qd9zynr
  - type: blocks
    target: is-01m2h3vkgbkeq82ch4mzkrch1g
  - type: blocks
    target: is-01m2p38vk3d6gkv2ts21bzfzw3
  - type: blocks
    target: is-01m2zvffb1z2vsseb9d9nqcj6m
  - type: blocks
    target: is-01m35ypert7n967xft0evk0qwc
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-16T01:07:30.107Z
updated_at: 2026-09-23T01:39:46.073Z
started_at: 2026-09-16T21:12:28.687Z
---
Independently review the repository URL reducer and URL-open slice over the reviewed shared repository store and immutable Git-tree source. Resolve findings through the review shortcut, run make verify, and publish one formal GitHub PR with gh based on the exact named convergence head recorded by mb-j439. Prove a repository-root URL opens a full-OID subject with no checkout or network on a valid hit. Record PR URL, base/head branches and OIDs, formal stack view, review evidence, final green CI, and mb-n2ro registration. Do not merge.
