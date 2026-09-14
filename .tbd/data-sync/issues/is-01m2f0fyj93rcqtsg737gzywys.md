---
type: is
id: is-01m2f0fyj93rcqtsg737gzywys
title: "PR #114 review R3: nested-link-label regressions in wiki-parser bracket pairing (stale ')' miss memo; links inside link text)"
kind: bug
status: open
priority: 2
version: 1
labels:
  - markdown
dependencies: []
parent_id: is-01m2f0fb55v9h6480r6cfx514k
created_at: 2026-09-14T03:48:38.089Z
updated_at: 2026-09-14T03:48:38.089Z
---
PR #114 review R3 (Low). src/metabrowser/builtin_plugins/markdown/wiki-parser.js:660-681, 712-758, 784-803. (a) findCharacter caches a ')' miss that is reused for an earlier start: [x [b]([[W]]) d](e converts W inside a real link. (b) CommonMark forbids links inside link text: in [a [b](c) [[W]]](e) the outer brackets are not a link, but W stays literal. Fix: next-')' table in the lazy pass; deactivate openers that contain a link. Add both inputs to bracketPairingCases.
