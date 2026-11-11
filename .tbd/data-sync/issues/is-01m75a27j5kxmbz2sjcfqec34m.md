---
type: is
id: is-01m75a27j5kxmbz2sjcfqec34m
title: "PR #351 A6: redundant font-size rule and unrecorded exception to the revision size rule"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m75a1p5xdgrc0v0e1pxfpct9
hold: null
hold_until: null
created_at: 2026-11-11T12:41:59.108Z
updated_at: 2026-11-11T12:57:04.058Z
started_at: 2026-11-11T12:57:02.141Z
closed_at: 2026-11-11T12:57:04.057Z
close_reason: "fixed in 970dbbc0: font-size removed from .github-pull-external-action; exception recorded in styles.css and the Chrome table; design test asserts both"
resolution: null
duplicate_of: null
---
Low. github/styles.css:184-186, 333-338. Keep one declaration; record the exception in design-system.md. PR #351, review A (https://github.com/jlevy/metabrowser/pull/351#pullrequestreview-5855489961).
