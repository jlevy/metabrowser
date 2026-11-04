---
type: is
id: is-01m6ja4vx6617n2t5ks5k0pcn7
title: Decorate protocol-relative GitHub destinations after Markdown resolution
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/design-system.md
labels: []
dependencies: []
parent_id: is-01m6j7mjcjmn42yqwcqvwbwkwq
created_at: 2026-11-04T03:37:51.268Z
updated_at: 2026-11-04T03:37:51.268Z
---
Independent productionMarkdown probe replaces only externalissuehref with //github.com/another/repo/issues/23. Resolver preservesvalidprotocol-relativehref; newURLwithoutbase omitsneutralentityicon. Existingfullenhancerrunnerpasses; exactchangedcasefails expectedmarkassertion. Resolveprotocol-relativeagainstlocaldocumentorigin while preserving rawURLchecks, exacthosts/credentials/ports and ordinaryrelative/internal neutrality. Authorfixinprogress beforefreeze. Evidence github-links-b85cd1f4/protocol-relative-markdown-probe.cjs andred.log.
