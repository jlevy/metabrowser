---
type: is
id: is-01m82c8abm03xzpvctgea74ywj
title: "Nightly soak 2026-11-21 (run 44905073328): nav-reveal Chrome address step finds no row for /view/docs/deep/deeper/leaf.md on main 98c2dffd4"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
created_at: 2026-11-22T19:38:14.258Z
updated_at: 2026-11-22T19:38:14.258Z
---
Nightly soak chrome (4, 4/4): tests/dom/nav-reveal-chrome.mjs:141 'failed the address: the row is selected / in view', row null, selectedFiles []. Same test family as closed mb-551m, so that fix did not hold or a second mechanism exists. Check mb-a124 (fixture accepting a different server on the same port) as a candidate cause. Find the mechanism before the 0.13.0 candidate.
