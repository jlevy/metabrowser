---
type: is
id: is-01m0jswnf4rw62apq363dvjrgz
title: Parity table and devtools/check_parity.py
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-21-cli-parity-and-golden-coverage.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0jswnx3xp7xegyxnk3a2bv9
  - type: blocks
    target: is-01m0jsxgty51qvw61s6sfwv688
parent_id: is-01m0jsvvcqw7knvxbaq4sn6ddj
created_at: 2026-08-21T18:38:48.803Z
updated_at: 2026-08-28T07:48:15.100Z
closed_at: 2026-08-28T07:48:15.090Z
close_reason: check_parity.py enforces the parity table in make lint/lint-check with 8 tests covering each failure mode; the rule is in AGENTS.md and its reasoning in docs/development.md. Table starts honest at 2 covered, 20 gap, 2 exempt.
resolution: null
duplicate_of: null
---
Add the parity column to docs/project/architecture/arch-views-models-routes.md, the one document that already fails the build when its tables drift, and a check wired into make lint and make lint-check beside public_hygiene. It enumerates routes from server.py, git/routes.py, and every manifest data hook, plus kinds and views from the manifests, then fails when a surface has no row, when a row names a metab invocation the CLI does not accept, when a row's command appears in no golden, or when an exemption carries no reason. Today's gaps go in as explicit gap rows so the table is honest on day one. Needs its own tests: a missing row, a row naming a command that does not exist, and a row whose command appears in no transcript must each fail with the surface named.
