---
type: is
id: is-01m6fr98p96cyrxrqs4aaz4r0x
title: "PR #284 D5: store_tag reads info/attributes on every comparison request and page serve"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6fr829v5p0bx9wm4rr3z5wj
hold: null
hold_until: null
created_at: 2026-11-03T03:47:12.200Z
updated_at: 2026-11-03T03:52:30.492Z
started_at: 2026-11-03T03:47:30.616Z
closed_at: 2026-11-03T03:52:30.491Z
close_reason: "fixed in e610ebab: store_tag keeps each store's tag with the stat of its attributes file, one stat a call; 25.8 us to 6.9 a call with a small file, 1276 to 6.8 with 1 MiB; test_a_store_tag_is_read_once_and_follows_every_edit counts the reads"
resolution: null
duplicate_of: null
---
Low. src/metabrowser/http_caching.py:105-107 opened and read up to 1 MiB synchronously on the event loop per request (sidekick.py:329, server.py:1395). Review D: https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5746804338. Fix: the tag is kept per store with the stat of the file it was made from; one stat a call; measured before and after.
