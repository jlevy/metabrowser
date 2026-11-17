---
type: is
id: is-01m7kh4k0qtd75277xcq14dt1b
title: CI takes ~20-25 minutes per push; assess end to end and design how to get the PR gate to 3-5 minutes with the same coverage
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-17T01:14:58.454Z
updated_at: 2026-11-17T01:14:58.454Z
---
Owner, 2026-11-16: 'investigate why CI is taking so long. This is unacceptably slow for CI. CI should be something like 3 to 5 minutes, or else we should figure out ways to avoid extraneous checks except when they're appropriate. ... properly assess this end-to-end and what the proper engineering solution is to maintain the same levels of coverage but speed up our development velocity.' Deliverable: a research brief and plan PR with implementation beads; workflow-file changes need the owner's OK (no grant covers workflow files).
