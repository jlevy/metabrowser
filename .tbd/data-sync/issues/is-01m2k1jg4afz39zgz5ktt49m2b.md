---
type: is
id: is-01m2k1jg4afz39zgz5ktt49m2b
title: "Hosted review Phase 0A.7: review and publish the formal stacked draft PR"
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
dependencies:
  - type: blocks
    target: is-01m2k1jj8edebds7zv8abfc917
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
created_at: 2026-09-15T17:24:27.913Z
updated_at: 2026-09-15T18:57:05.661Z
---
Run the tbd precommit and code-review shortcuts, make verify, and tbd sync; review the exact diff for forbidden provider, network, cache, route, view, manifest, lockfile, and dependency changes. Push codex/v011-hosted-review-phase0a and open a draft GitHub PR based on codex/v011-hosted-review-design. Record the stack dependency on PR 125, exact validation, and follow-up Phase 0B blockers; watch all GitHub checks to a final green summary.

## Notes

Precommit and review shortcuts loaded. Three Fable closure passes reviewed architecture, Python/browser contract semantics, corpus portability, and delivery scope; all findings were addressed and the final architecture/contract passes report no actionable findings. Final make verify passed 2,148 tests (1 skipped), 124 goldens, strict lint/type/parity/hygiene, npm and Python audits, wheel/sdist inspection, exact nine-plugin dormancy, and isolated-wheel smoke. Draft stacked PR publication and GitHub CI remain.
