---
type: is
id: is-01m0jswnx3xp7xegyxnk3a2bv9
title: Codify the parity principle in AGENTS.md and development.md
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-cli-parity-and-golden-coverage.md
labels: []
dependencies: []
parent_id: is-01m0jsvvcqw7knvxbaq4sn6ddj
created_at: 2026-08-21T18:38:49.250Z
updated_at: 2026-08-21T18:38:49.250Z
---
State the rule where it is binding and keep it short, because the check is what enforces it: every route, kind, and model the browser consumes has a metab equivalent and a golden transcript; check_parity.py names what is missing; the exemption list and its reasons live in the map document. The reasoning — why parity is stated at the model layer, why the view layer is exempt, and why transcripts beat integration suites here — goes in docs/development.md. Follows the AGENTS.md meta-rule: prefer a check to a sentence, and state the reason with the rule.
