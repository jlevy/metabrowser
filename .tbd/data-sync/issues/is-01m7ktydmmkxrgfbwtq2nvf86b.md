---
type: is
id: is-01m7ktydmmkxrgfbwtq2nvf86b
title: "PR #496 review A2: after-merge coverage depends on someone reading a red main (Q6 open)"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7ktycr1m7798eaqhyky3qnr
created_at: 2026-11-17T04:06:22.100Z
updated_at: 2026-11-17T04:08:31.578Z
closed_at: 2026-11-17T04:08:31.577Z
close_reason: "Fixed in 8b4da0cb: the plan job reads main's newest ci.yml run with actions: read; while main is red a pull request runs main's whole matrix and ci-ok names main's run; the merging agent watches main after each merge (procedure into AGENTS.md by mb-oz36). Q6 decided."
resolution: null
duplicate_of: null
---
plan:7-9, :186-188, :572-576, :608-611 at 1e6f437f. Naming the commit that broke main is not telling anyone; with ci-ok required, later pull requests stay green on 3.13 and keep merging. Decision: ci-ok fails while main is red, and the merging agent watches main after each merge; the plan says how ci-ok learns main is red.
