---
type: is
id: is-01m7k4rbwpzbrxkf1686cpsmrm
title: A status count reads in its status's ink and bold, number and letter alike ('21 A, 15 M, 7 D'), with muted punctuation, the same on every surface
kind: feature
status: closed
priority: 1
version: 7
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
child_order_hints:
  - is-01m7kbhyshb2h9kge2nwjedeq3
  - is-01m7kbhzp7s2f41yaa9d79cwma
  - is-01m7kbj0fw9rg2pepcrzfprnkx
  - is-01m7kbj17nkr7ssf1xkcv2rr0x
hold: null
hold_until: null
created_at: 2026-11-16T21:38:35.027Z
updated_at: 2026-11-17T01:09:31.982Z
started_at: 2026-11-16T21:39:21.885Z
closed_at: 2026-11-17T01:09:31.981Z
close_reason: "Status counts bold in their status ink everywhere, merged in #489"
resolution: null
duplicate_of: null
---
Owner, 2026-11-16: 'the 21 A, 15 M, 7 D etc on the [diff] summary abbreviated form should use the appropriate A/M/D colors and boldface for both number and letter, all bold on each, and muted gray for punctuation' and 'this should be the same everywhere'. Today (#479) the number is bold in the line's ink and the letter is regular in the status ink. Change the one painter (countPartsNodes / countPartsHtml / changeLine*) and move every surface that shows status counts onto it: the Diff summary header, the brief change line, the commit hover card, the commit totals line, the stack headings (#484), and any other status tally.
