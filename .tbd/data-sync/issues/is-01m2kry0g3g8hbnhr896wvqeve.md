---
type: is
id: is-01m2kry0g3g8hbnhr896wvqeve
title: "Hosted review Phase 0C.2b: review and publish the format-boundary phase"
kind: task
status: in_progress
priority: 1
version: 20
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - phase:hosted-review-0c2
dependencies:
  - type: blocks
    target: is-01m2k1jrywxceb6n3r0pbadegx
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
  - type: blocks
    target: is-01m2kwk6h6pzxanejy6c339r08
parent_id: is-01m2k1jrywxceb6n3r0pbadegx
child_order_hints:
  - is-01m2mj2zrph9kmh788v80mv0d1
  - is-01m2mj992qt7r9jx22dm9f25j8
  - is-01m2mja6bfq04nsza220t8yhsa
  - is-01m2mk1jrtcafrmy046gc53jt2
  - is-01m2mk1k3t90h99zszfa8pq9c1
  - is-01m2mk1ke5hfv4pzj4ytr28ma9
  - is-01m2mk1krjjyh70r8gjcjjkg0n
  - is-01m2mk1m3195p46j7y4jmmw3wx
  - is-01m2mk1mdfdj5eq8znnr2gk0bp
  - is-01m2mk1mr2m79ccpe21yyzd49c
  - is-01m2mmctkaezwfx0rq66tqafyp
  - is-01m2mmdf9mpymtnhrehbe4y5e9
  - is-01m2mmgq4qcwk5xb6pxsmea8g0
  - is-01m2mmgqnq6m6jmta0ekt0rxk7
created_at: 2026-09-16T00:12:42.370Z
updated_at: 2026-09-16T08:14:47.478Z
---
Run independent inventory, installed-wheel, parity, architecture, and delivery reviews; address every finding; run make verify; sync beads; and publish exactly one formal draft Phase 0C.2 PR with gh, based on the exact green Phase 0C.1 head. Record base/head OIDs and stack path, watch GitHub CI to a final green summary, and register the PR with mb-n2ro. Do not merge here; mb-n2ro alone owns explicit-approval landing and retargeting, and mb-63ym closes only after every Phase 0 PR is landed and revalidated.

## Notes

Independent Fable-style reviews completed with seven unique actionable findings, all tracked before fixes: mb-va6q ambient Python isolation; mb-ey4z independent provider completeness; mb-0wdq explicit browser-consumption modeling; mb-4ng5 positive and negative corpus evidence; mb-5qo7 serialization and artifact-profile round trips; mb-rjz2 browser-portable self-contained parser execution; mb-9obp installed sdist capability evidence. The pre-fix baseline make verify passed with 2325 tests plus 124 goldens, audits, artifact inventory, parity, and distribution. Three subagents now own disjoint fix groups; all review beads remain in progress until PR disposition.
