---
type: is
id: is-01m84frddm4hytc6q59eqptsbn
title: "File Overview: put the type legend in a right column on wide screens"
kind: feature
status: closed
priority: 2
version: 6
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/757
    at: 2026-11-23T16:09:40.597Z
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T15:17:56.275Z
updated_at: 2026-11-23T18:01:51.257Z
started_at: 2026-11-23T15:52:28.899Z
closed_at: 2026-11-23T16:09:41.090Z
close_reason: "The legend is a rail on the TOC's track in the wide band, and unchanged in narrower bands. Measured in Chrome and pinned in the README TOC session. In #757."
resolution: null
duplicate_of: null
---
Under File Overview the type legend sits below the bars. At the width where a README shows its table of contents on the right, show the legend as a vertical list in a column to the right of the type bars and the compact treemap. Use the TOC's breakpoint and its horizontal position. Narrower screens keep the legend below the bars. Requested in manual testing of the treemap stack.

## Notes

Follow-up on layer 6 (#757): tests/dom/reading-column-chrome.mjs now ends the centered column at the legend rail; CI's Chrome tier had failed three folder cases (1920/2560 px folder hidden, collapsed README) because the test ended the column at the card.
