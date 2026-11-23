---
type: is
id: is-01m836r7jghtaq3hc7q5cny9sw
title: "Address review A on #723 (treemap layer)"
kind: task
status: closed
priority: 2
version: 15
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
child_order_hints:
  - is-01m83cebrt3h0we1ncr8f8rt0h
  - is-01m83cegkb1xvwymazrefqp1wr
  - is-01m83cepszrj802g2kvyypgj3f
  - is-01m83cewern2v804vysmfh3z8s
  - is-01m83cf4d7mk59w23bv8syv0pw
  - is-01m83cf9vaj133w5hrbw3c9qvd
  - is-01m83cfgxjcqqy4d65tr0sxxff
  - is-01m83cfpj7vjwvrnhmjsep0q6t
  - is-01m83cfwy3evdmaepc5g0v1bd4
  - is-01m83cg2m1f2sq3sj6sz028fe1
  - is-01m83cg5fnaktd3n3sxt0a5fww
  - is-01m83cg9d8x6agdesm4cwjfd34
hold: null
hold_until: null
created_at: 2026-11-23T03:21:18.663Z
updated_at: 2026-11-23T05:31:23.825Z
started_at: 2026-11-23T03:22:06.881Z
closed_at: 2026-11-23T05:31:23.825Z
close_reason: every finding of review A has a disposition, posted on the PR at the pushed head
resolution: null
duplicate_of: null
---
Review https://github.com/jlevy/metabrowser/pull/723#pullrequestreview-6016187092. A1 High: CSS padding+border floor widens tiny cells past their parents (same as mb-coqj); fix + Chrome containment check. A2 Medium: framing hides labels that fit; nest under a header whenever the label fits. A3 Low: a folder with children [] and only rest gets a frame around one inert remainder; don't nest it. A4 Medium: no regression test for the padding-box measurement. A5 Low: treemapRollupQuery vs docs/plugins.md:887. A6 Low: settings.py 'twelve levels is deeper than the map can draw' is wrong; re-measure the ROLLUP_BODY_CACHE_ENTRIES body size for depth 12/top 200. A7 Low: repoint styles.css:111,121-122, test_design_vocabulary.py:1521-1522, parity row owners at treemap-map.js. A8 Low: test_modified_keys.py:192 compact mention belongs in #724. A9 Low: doc that a framed folder is its own keyboard control. A10 Low: measure a full relayout at maxCells in Chrome and record it. A11/A12 suggestions: framed offset assertion, rest-in-parent check, one data-tm-index per actionable cell; justify frameNestMinPx and minNestShare.
