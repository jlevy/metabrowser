---
type: is
id: is-01m7hhgrb3grtwjxsvemh3yacj
title: "PR #474 A9: Pulls count and Checks summary weights guarded only indirectly"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hg857dzfenxr1hee0jd9ka
hold: null
hold_until: null
created_at: 2026-11-16T06:43:08.258Z
updated_at: 2026-11-16T07:10:07.266Z
started_at: 2026-11-16T06:43:16.106Z
closed_at: 2026-11-16T07:10:07.265Z
close_reason: "fixed in 40ef87afd: co-class font-weight guard and Checks paragraph guard; nav-metadata-chrome reads the Pulls count number at 700"
resolution: null
duplicate_of: null
---
Low suggestion. test_design_vocabulary.py:2146-2151; nav-metadata-chrome.mjs:318-333. Suggestion: read the Pulls count numeral's computed weight in Chrome, or add the co-class to the guard. Review A round 1 on PR #474: https://github.com/jlevy/metabrowser/pull/474#pullrequestreview-5915978133
