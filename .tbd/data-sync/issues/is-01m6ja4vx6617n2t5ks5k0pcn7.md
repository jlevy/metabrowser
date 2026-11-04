---
type: is
id: is-01m6ja4vx6617n2t5ks5k0pcn7
title: Decorate protocol-relative GitHub destinations after Markdown resolution
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/design-system.md
labels: []
dependencies: []
parent_id: is-01m6j7mjcjmn42yqwcqvwbwkwq
created_at: 2026-11-04T03:37:51.268Z
updated_at: 2026-11-04T17:14:29.659Z
closed_at: 2026-11-04T17:14:29.659Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Independent productionMarkdown probe replaces only externalissuehref with //github.com/another/repo/issues/23. Resolver preservesvalidprotocol-relativehref; newURLwithoutbase omitsneutralentityicon. Existingfullenhancerrunnerpasses; exactchangedcasefails expectedmarkassertion. Resolveprotocol-relativeagainstlocaldocumentorigin while preserving rawURLchecks, exacthosts/credentials/ports and ordinaryrelative/internal neutrality. Authorfixinprogress beforefreeze. Evidence github-links-b85cd1f4/protocol-relative-markdown-probe.cjs andred.log.
