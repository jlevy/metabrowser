---
type: is
id: is-01m7hhq7nhskwg5f3hync4ytsc
title: "Conversation: a wrapped commit row ending on its monospace hash leaves 22.5 px to the next event instead of the 20 px rhythm"
kind: bug
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
created_at: 2026-11-16T06:46:40.560Z
updated_at: 2026-11-20T17:10:09.382Z
---
Found while addressing #461 review A1: at 420 px a wrapped commit row can end on a line holding only its 13 px monospace hash; its glyphs leave 2.5 px of the 19.5 px line empty, so 22.5 px shows below the row (Chrome 152). The timeline Chrome test allows 3 px there. Fix by aligning the hash's line box with the subject's, then tighten the test.
