---
type: is
id: is-01m2zwj2wpj4abvhdng36mnm03
title: "S209-8: PR 209 has never been validated in a real browser, and three spec test-strategy items are unexercised"
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr209
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T17:06:59.092Z
updated_at: 2026-09-21T07:17:25.863Z
closed_at: 2026-09-21T07:17:25.862Z
close_reason: "Merged to main as c09db6b2 (PR 221). The three spec test-strategy items now execute: relative-reference resolution through /raw/{path}, nested frames and a frameset with the frame-ancestors regression guard, and the dangerous types beyond html and svg. Each verified by mutating the server at runtime and confirming the test catches it. No defects found. The real-browser half of this bead was covered manually by the user against a hostile fixture on 2026-09-20."
resolution: null
duplicate_of: null
---
All evidence for PR 209's containment is header assertions on the wire plus a browserless DOM session against the production plugin JS. No one has loaded a hostile page in a real browser and observed the sandbox hold. Spec testing-strategy items with no test: (1) relative references end to end, a page with a sibling stylesheet AND a subdirectory image fetched from the expected /raw/ paths; (2) a nested same-directory iframe and a frameset page actually loading (regression test for the deliberately absent frame-ancestors); (3) dangerous types on the wire beyond html and svg: xhtml, xml, pdf, js, extensionless. Do a scripted real-browser pass using the manual plan recorded in the PR 209 disposition, record results on the PR, and add the three missing tests.

## Notes

2026-09-20: real-browser validation DONE by the user against a hostile fixture served by the PR 209 build (head 04534249): preview default, relative references, nested frame, every sandbox probe blocked; reported as working well. Server side confirmed with curl on the live build (sandbox headers on 200 and 400, Origin null and cross-site text/plain POST get 403, fragment defaults to Source). Note: the desktop built-in browser pane blocks the sandboxed subframe with ERR_BLOCKED_BY_CLIENT, so it cannot be used for this check. REMAINING: the three missing automated tests (relative references end to end with a subdirectory image; nested iframe and frameset loading; dangerous types on the wire beyond html and svg). The PR 209 description is stale (head SHA, 'do not merge' line); an automated edit was blocked by the permission layer, so it needs a manual edit or an allow rule.


The parent of this bead is:
---
type: is
id: is-01m2yxd3tnr1s2zf0h0jat1ey2
title: "v0.11 stabilization review: independent full review of stack #218 and #209 against specs and beads"
kind: task
status: in_progress
priority: P1
version: 48
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
# Blocks: mb-n2ro
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
… [93 lines omitted]

Real-browser validation is DONE (user confirmed on 2026-09-20). What remains is only the three automated tests.
