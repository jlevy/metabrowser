---
type: is
id: is-01m03ykbc3ssm728mkgkje7c2p
title: kpress CI blocked by nanoid advisory GHSA-2v37-7h3g-55p8
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-16T00:12:29.954Z
updated_at: 2026-08-16T01:27:25.051Z
closed_at: 2026-08-16T01:27:25.048Z
close_reason: null
---
The kpress lint job fails at 'npm audit --audit-level=moderate' on a high-severity advisory in nanoid <3.3.18 (GHSA-2v37-7h3g-55p8), a transitive npm dependency. Lint, supply-chain, public-hygiene, and flowmark all pass; only the audit step fails, and every test/distribution job passes. Pre-existing and unrelated to any single PR: kpress main last built green on 2026-08-10, before the advisory, and https://github.com/jlevy/kpress/pull/48 changes no dependency file. It will block every kpress PR until nanoid is bumped, which is a deliberate supply-chain change under SUPPLY-CHAIN-SECURITY.md (exact pin, cool-off rules) rather than something to fold into an unrelated PR.
