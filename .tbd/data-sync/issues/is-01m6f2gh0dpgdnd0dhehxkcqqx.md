---
type: is
id: is-01m6f2gh0dpgdnd0dhehxkcqqx
title: "PR #272 https://github.com/jlevy/metabrowser/pull/272#discussion_r4447865372: zero-limit changelog sentence overstates the decompression parse error"
kind: bug
status: closed
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m6f1c0tknva4bd436kj524e0
created_at: 2026-11-02T21:26:41.419Z
updated_at: 2026-11-02T21:43:01.626Z
closed_at: 2026-11-02T21:43:01.625Z
close_reason: "fixed in b49dfe40: CHANGELOG.md says truncated when the start of the stream decodes and a parse error when it fails before that; test_parsed_endpoint_under_a_cap_too_small_for_a_compressed_file_reads_only_its_start holds both. Reply: https://github.com/jlevy/metabrowser/pull/272#discussion_r4448121261"
resolution: null
duplicate_of: null
---
Unmarked bot comment, bot severity Medium, on commit 38447bdc. CHANGELOG.md:996-999. Review A's A1 discussion thought the sentence's hedge sufficient; the same runs show a stream damaged after its start answers truncated at limits 0 and 1.

## Notes

Fixed in b49dfe40. Thread reply and listing held with mb-p9y7 until the coordinator decides that escalation, since both comments are one qodo review object (5743496320). Close after the reply is posted.
