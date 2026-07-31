---
type: is
id: is-01kytxx3fqx0xe3f9w60et58vv
title: Upgrade tbd to 0.4.2 and re-apply repo hardening to installed hooks/scripts
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-07-31T01:51:29.270Z
updated_at: 2026-07-31T01:51:50.397Z
closed_at: 2026-07-31T01:51:50.396Z
close_reason: null
---
Upgraded get-tbd 0.4.1->0.4.2 globally (first-party cool-off exemption), ran tbd setup --auto, merged upstream setup-github-cli doc fork, re-applied repo hardening: root-anchored hook commands, get-tbd version pin in skills, graceful skip on unsupported gh platforms.
