---
type: is
id: is-01m0jswnx3xp7xegyxnk3a2bv9
title: Codify the parity principle in AGENTS.md and development.md
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-cli-parity-and-golden-coverage.md
labels: []
dependencies: []
parent_id: is-01m0jsvvcqw7knvxbaq4sn6ddj
created_at: 2026-08-21T18:38:49.250Z
updated_at: 2026-08-28T03:59:12.559Z
---
Add the parity principle to AGENTS.md, pointing at the check rather than restating it, and put the reasoning in docs/development.md, which today does not mention parity at all.

The rule has three clauses:

1. Every route, kind, and model the browser consumes has a metab equivalent and a golden transcript.
2. State clause: every state the system persists is reachable from metab as a normalized model and pinned by a golden. Cache layout, entry identity, entry state, and reclamation outcomes are read through /api/cache/* like any other model, not through a bespoke inspection command.
3. Prefer adding a route to adding a CLI mode. --api reaches routes by construction, so a surface exposed as a route is inspectable and golden-pinned for free, while a surface exposed only as a CLI mode needs its own flag, its own normalizer path, and its own golden.

devtools/check_parity.py enforces clause 1; the exemption list and its reasons live in docs/project/architecture/arch-views-models-routes.md. Clauses 2 and 3 are stated in docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md.
