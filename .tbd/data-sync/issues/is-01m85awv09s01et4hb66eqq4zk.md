---
type: is
id: is-01m85awv09s01et4hb66eqq4zk
title: "PR #766 A12: KPress drops text after a bare <td>/<th> (Document view too)"
kind: bug
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01m8577az40f83ecdxrw97hmth
created_at: 2026-11-23T23:12:12.803Z
updated_at: 2026-11-24T00:37:18.422Z
---
Low finding A12 of review A on PR #766 (https://github.com/jlevy/metabrowser/pull/766#pullrequestreview-6030955099). At KPress postprocessor.

## Notes

Deferred from PR #766 review A (A12) at the coordinator's decision: not this PR. Verified 2026-11-23 on '# Title\n\n<td>\n\nA paragraph after.\n\nAnother one.\n': CommonMark (markdown-it-py commonmark and gfm-like) renders <td> as an HTML block and both paragraphs; GitHub (gh api markdown, mode=gfm) drops the stray tag and shows both paragraphs; KPress 0.3.9 parse_markdown shows only the heading, since _postprocess_html buffers the cell and never flushes it (the sanitizer alone keeps the paragraphs). The projection answers ready, source_only true, the heading as context only. Filed in KPress as kpr-gtv7 under kpr-t59f. Metabrowser follow-up once KPress fixes it: a test that the paragraphs project as added; meanwhile the reviewer's projection-side option (a unit whose Markdown text renders nothing falls back to one block) is open.
