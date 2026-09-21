---
type: is
id: is-01m2yxd3tnr1s2zf0h0jat1ey2
title: "v0.11 stabilization review: independent full review of stack #218 and #209 against specs and beads"
kind: task
status: in_progress
priority: 1
version: 47
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
child_order_hints:
  - is-01m2zpvykba6wabg6ms9wawzb0
  - is-01m2zpvzfx40az8dvj2peg3hb2
  - is-01m2zpw18m2z2nmprgkmzq3jwk
  - is-01m2zpw31yzxj69k3fdzzp3qn7
  - is-01m2zpw4zkmx00dk5gh5s4kjqm
  - is-01m2zpw6dzfwa6a86z4vc8yfzc
  - is-01m2zpw7z0f201xxwtvzb51kyk
  - is-01m2zpw9bkkn7m6gwv0q5cbeqd
  - is-01m2zpway7zvshv7271v9cp498
  - is-01m2zpwenhppjpks39tf0nxkkb
  - is-01m2zpwg44k0y7snevbfqdyw8k
  - is-01m2zpwhgmcptq6ge42ckj84rc
  - is-01m2zpwjvq4pq1cqbdqa1avrp3
  - is-01m2zpwm7b0ns673t2jyje7fdg
  - is-01m2zpwnbv0z16dxng8s75dn4b
  - is-01m2zpwpet6pzt8zvvmnx082ac
  - is-01m2zpwqfy7v676azc2mxx3g5s
  - is-01m2zpwrm0069gs0swx9m6xqfr
  - is-01m2zpwswpwq4hm7kr70ddpbjy
  - is-01m2zpwtxsex7zg035m9p3yvm7
  - is-01m2zpwvxd9vp6vpn587bsz6p7
  - is-01m2zpwxfk2v9gqyrt5yg6a59x
  - is-01m2zpwyzk68zpmngrxadssn2r
  - is-01m2zpx0fhq4x5e1qtcteearj5
  - is-01m2zpx1svn4c8an4mm9r9mv8z
  - is-01m2zpx351fryc2z9hjb2m4j4a
  - is-01m2zpx4d15neap9x8fcf36tq4
  - is-01m2zpx5m27d6tnn4qf6zbhfv8
  - is-01m2zpx6gr7kcfmwvbrfhbse7s
  - is-01m2zpx7pmkbxzgkp7cwqt6qzb
  - is-01m2zpx9218wz0egrejamr3651
  - is-01m2zpxck1jqrmv4a2dhwve47v
  - is-01m2zpxg6x10hmbxayqh9ccag1
  - is-01m2zpxmwz32ykx0q3w62qhghh
  - is-01m2zpxqcyxkb5ajsh9zm2c47p
  - is-01m2zpxv9y2v992te1pdr2x52n
  - is-01m2zpxwxtv9pcjf6ynxcan41h
  - is-01m2zpxyf1qczg3r6cadfhh7sy
  - is-01m2zvfm9pdxz0emydeqedf9gq
  - is-01m2zwj2wpj4abvhdng36mnm03
  - is-01m2zyv9gj9f0w6esn4vnsy38s
created_at: 2026-09-20T08:02:30.356Z
updated_at: 2026-09-21T00:32:31.930Z
---
Follow-up to mb-rldx, which was closed at 2026-09-20T07:32Z by a fast pass while its own notes said the #216 browser/plugin, resource-lifecycle, CLI/parity, and docs review passes were unfinished. Independently verify the #140/#217/#216 fix commits (da73b878, 70091d81, bc8dd72b, de0f4f5a), complete the unreviewed areas, review #209 as the security gate for serving acquired Git, reconcile every PR review channel, and reconcile beads and spec checklists with the branches. Output: confirmed findings filed as beads on their owning layers, and an ordered stabilization plan. Read-only until the plan is agreed; do not merge (landing owner is mb-n2ro).
