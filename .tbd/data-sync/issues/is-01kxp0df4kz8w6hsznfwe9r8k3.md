---
type: is
id: is-01kxp0df4kz8w6hsznfwe9r8k3
title: Simplify repository tooling policy into focused behavioral checks
kind: task
status: closed
priority: 1
version: 5
labels: []
dependencies: []
created_at: 2026-07-16T17:43:28.658Z
updated_at: 2026-07-16T18:40:18.192Z
closed_at: 2026-07-16T18:40:18.192Z
close_reason: Implemented, independently reviewed, and fully verified.
---

## Notes

Completed in d6a54f3. Replaced the 425-line npm policy monolith and brittle config-mirroring tests with a shared 144-line cross-file supply-chain checker and five focused tests. Removed pass-through npm wrappers and dead lifecycle configuration; aligned Make, CI, Lefthook, formatting, linting, testing, audits, builds, and docs around canonical tool configuration. The checker is byte-identical to KPress and covers npm >=11.10 release-age enforcement, exact direct npm specs, lock registry/integrity, matching nvm/fnm pins, uv cool-off, immutable GitHub and Docker actions, and trusted publishing. Independent review findings were fixed. Final make -j4 verify: 671 tests passed; lint, strict types, Biome, both tsc configs, Flowmark, public hygiene, supply-chain checks, npm/uv audits, build, distribution inspection, installed-wheel and six-plugin smoke all passed.
