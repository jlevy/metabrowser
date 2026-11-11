---
type: is
id: is-01m75a25jpjmwg49dfqfxwwksq
title: "PR #351 A1: check-row action correct only for GitHub Actions URLs"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m75a1p5xdgrc0v0e1pxfpct9
hold: null
hold_until: null
created_at: 2026-11-11T12:41:57.078Z
updated_at: 2026-11-11T12:57:02.491Z
started_at: 2026-11-11T12:57:00.474Z
closed_at: 2026-11-11T12:57:02.490Z
close_reason: "fixed in 970dbbc0: checks() classifies CheckItem.action once (actions/github/external, null for non-http(s)); GitHub kinds muted with leading mark, external uses --link; app hidden only beside an Actions link. Confirmed by checkRows in github-pull-page-mount-behavior.js and checkActions in cli-ui-github-pull-page.tryscript.md"
resolution: null
duplicate_of: null
---
Medium. pull-page.js:3341-3364, github/styles.css:333-346, design-system.md:1064-1067. Non-Action github.com checks show a trailing icon; non-GitHub View details looks like the detail; an ftp: URL renders a label with no link; link text and hidden detail decided by two rules. Fix: classify once in checks(). PR #351, review A (https://github.com/jlevy/metabrowser/pull/351#pullrequestreview-5855489961).
