---
type: is
id: is-01m7hdfmrcg2zy72pgekkb5hge
title: "PR #462 A2: no test places Quick Search's marks in the rest of a prefixed title"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjk31aveb74wwdggthjpq
hold: null
hold_until: null
created_at: 2026-11-16T05:32:37.515Z
updated_at: 2026-11-16T06:03:40.492Z
started_at: 2026-11-16T05:32:43.684Z
closed_at: 2026-11-16T06:03:40.491Z
close_reason: "fixed in e868488ea on #462: prefixed row in pullSearchSession with label shape pinned in cli-ui-quick-search; Chrome check asserts #ledger marks exactly [ledger]; start->0 mutation fails both. CI run 43812004069 green at 9758ea748. Reply: https://github.com/jlevy/metabrowser/pull/462#issuecomment-6908742029"
resolution: null
duplicate_of: null
---
Medium. PR #462 review A round 1 (https://github.com/jlevy/metabrowser/pull/462#pullrequestreview-5915416972). src/metabrowser/static/search-palette.js:484-488; tests/dom/title-prefix-chrome.mjs:371 and :551-560; tests/dom/search-palette-behavior.js:1207-1208. Mutation start->0 at search-palette.js:486 leaves every test green. Fix: prefixed pull row in pullSearchSession with a word in both parts, assert the label's shape; Chrome check asserts #ledger marks are exactly [ledger].
