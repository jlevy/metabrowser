---
type: is
id: is-01m836r7jghtaq3hc7q5cny9sw
title: "Address review A on #723 (treemap layer)"
kind: task
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T03:21:18.663Z
updated_at: 2026-11-23T03:22:06.933Z
started_at: 2026-11-23T03:22:06.881Z
---
Review https://github.com/jlevy/metabrowser/pull/723#pullrequestreview-6016187092. A1 High: CSS padding+border floor widens tiny cells past their parents (same as mb-coqj); fix + Chrome containment check. A2 Medium: framing hides labels that fit; nest under a header whenever the label fits. A3 Low: a folder with children [] and only rest gets a frame around one inert remainder; don't nest it. A4 Medium: no regression test for the padding-box measurement. A5 Low: treemapRollupQuery vs docs/plugins.md:887. A6 Low: settings.py 'twelve levels is deeper than the map can draw' is wrong; re-measure the ROLLUP_BODY_CACHE_ENTRIES body size for depth 12/top 200. A7 Low: repoint styles.css:111,121-122, test_design_vocabulary.py:1521-1522, parity row owners at treemap-map.js. A8 Low: test_modified_keys.py:192 compact mention belongs in #724. A9 Low: doc that a framed folder is its own keyboard control. A10 Low: measure a full relayout at maxCells in Chrome and record it. A11/A12 suggestions: framed offset assertion, rest-in-parent check, one data-tm-index per actionable cell; justify frameNestMinPx and minNestShare.
