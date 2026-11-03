---
type: is
id: is-01m6fr99m59j7fasd64w0cmhbq
title: "PR #284 Qodo: store_tag hashes only the first MiB of info/attributes, so an edit past it leaves the tag unchanged"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6fr829v5p0bx9wm4rr3z5wj
hold: null
hold_until: null
created_at: 2026-11-03T03:47:13.156Z
updated_at: 2026-11-03T03:52:31.122Z
started_at: 2026-11-03T03:47:30.631Z
closed_at: 2026-11-03T03:52:31.121Z
close_reason: "fixed in e610ebab: past the 1 MiB cap the file's size and modification time are in the tag, so an edit anywhere moves it; pinned by test_a_store_tag_is_read_once_and_follows_every_edit"
resolution: null
duplicate_of: null
---
Medium (bot). src/metabrowser/http_caching.py:56-58, 105-114. https://github.com/jlevy/metabrowser/pull/284#discussion_r4450318498 and, on the layer above, https://github.com/jlevy/metabrowser/pull/283#discussion_r4450564184. Fix: past the bound the file's size and modification time are in the tag, so any edit moves it; pinned in tests/test_http_caching.py.
