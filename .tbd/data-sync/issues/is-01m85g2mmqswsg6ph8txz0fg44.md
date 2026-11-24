---
type: is
id: is-01m85g2mmqswsg6ph8txz0fg44
title: Rendered diff spaces headings (h2 and others) differently from the Document view's serif document
kind: bug
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/780
    at: 2026-11-24T01:37:54.784Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
hold: null
hold_until: null
created_at: 2026-11-24T00:42:45.766Z
updated_at: 2026-11-24T01:38:02.075Z
started_at: 2026-11-24T00:45:21.964Z
closed_at: 2026-11-24T01:38:02.074Z
close_reason: |
  Cause: each block of a rendered Markdown diff is its own row, and each row had padding-block: 4px, which stops margin collapsing, so two blocks' KPress margins added up plus 8 px (paragraph to h2 52 px vs the document's 32; h2 to paragraph 36 vs 16; paragraph to paragraph 32 vs 12). Also KPress's ::details-content overflow: hidden kept an open fold's last margin inside it (24 vs 12). Fixed in PR #780 (diff/styles.css): rows set no block padding so margins collapse across rows; a changed block's band is drawn by ::before, --diff-markdown-band-extent past its text, moving no text; list/quote joins only between their own rows; h4-h6 + p carried across rows; open fold uses overflow: clip. Every pair now equals the Document view except an h3 straight after an h2 (+4.8 px; joining KPress's h2 + h3 would restate its margin). Not fixed here: tables lose .kpress-table-wrap because withoutRenderWrappers in static/inert-html.js unwraps a block's sole div. Evidence: tests/test_diff_markdown_spacing_chrome.py; measurements in explorations/performance-loop/design-rule-measurements.md "Rendered Diff Block Spacing".
resolution: null
duplicate_of: null
---
