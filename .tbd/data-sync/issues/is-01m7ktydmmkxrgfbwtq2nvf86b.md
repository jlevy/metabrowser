---
type: is
id: is-01m7ktydmmkxrgfbwtq2nvf86b
title: "PR #496 review A2: after-merge coverage depends on someone reading a red main (Q6 open)"
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7ktycr1m7798eaqhyky3qnr
created_at: 2026-11-17T04:06:22.100Z
updated_at: 2026-11-17T04:06:22.100Z
---
plan:7-9, :186-188, :572-576, :608-611 at 1e6f437f. Naming the commit that broke main is not telling anyone; with ci-ok required, later pull requests stay green on 3.13 and keep merging. Decision: ci-ok fails while main is red, and the merging agent watches main after each merge; the plan says how ci-ok learns main is red.
