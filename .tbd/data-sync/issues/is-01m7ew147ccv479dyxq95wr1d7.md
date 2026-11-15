---
type: is
id: is-01m7ew147ccv479dyxq95wr1d7
title: Files type filter menu is too short for its rows
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-15T05:49:07.179Z
updated_at: 2026-11-15T05:49:07.179Z
---
The user's request (2026-11-15), verbatim: "the height of that menu should be taller if it has more items. Approximately double the size for a max height. it holds about 8 lines but should hold more like up to 16, but appropriate to the number of items and always within the window". Then: "(the age drop down is fine as it has only a few items)".

"That menu" is the Files tab's type filter dropdown. On main, every filter chip menu uses `.chip-menu-panel` in `static/styles.css`, with `max-height: 320px; overflow-y: auto`. That holds about 8 rows plus the section headings.

Done when:
- the type filter menu takes its content's natural height, up to about 16 rows;
- the cap is expressed from the row height (a token or rows × the row's measured height, not a bare pixel guess);
- the menu always stays inside the window: it is capped by the space between its trigger and the window's edge, re-measured on open and on window resize, and scrolls inside itself past that;
- the age menu, which has few rows, is unchanged in size;
- the cap and the in-window rule are measured and pinned in a real browser at a tall and a short window.

Same menu as mb-s6vu (group headings), so they go in one PR.
