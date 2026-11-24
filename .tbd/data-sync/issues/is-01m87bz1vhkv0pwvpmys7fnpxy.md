---
type: is
id: is-01m87bz1vhkv0pwvpmys7fnpxy
title: "PR #771 A6: the PR description is stale against the KPress 0.3.10 release"
kind: bug
status: closed
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01m87bxfh1ymbm8c10h6rzs8gx
created_at: 2026-11-24T18:09:22.799Z
updated_at: 2026-11-24T19:23:07.284Z
closed_at: 2026-11-24T19:23:07.282Z
close_reason: "PR #771's description corrected for review A6 at head 96e13f0a5: Summary allowlist and projection bullets (A1, A2, A3, A7), the KPress 0.3.10 section (KPress removes the link and the typeless input), Known gap 1 rewritten from a headless-Chrome re-run at 0.3.10 (bullet lists closed; an ordered list keeps its number on inert surfaces), the test plan, and the guide re-pinned to 7c4bd886b..96e13f0a5 with a step for _RawMarkup and _inline_change; route_check: 10 of 10 steps ready."
resolution: null
duplicate_of: null
---
Low. PR body: KPress 0.3.10 section, Known gaps, test plan, guided review note. The coordinator maintains the body. PR #771, review https://github.com/jlevy/metabrowser/pull/771#pullrequestreview-6044731578

## Notes

Left to the coordinator, who maintains the PR body and its guided-review block. Corrections needed (head 96e13f0a51001af25a402a6d316650684fb21e28):

1. Summary, allowlist bullet: "keeps an `input` only as a task list's box" -> "keeps an `input` only in the shape of a task list's box, wherever the document writes a checkbox (a raw `<input type="checkbox">` in a paragraph or a table cell is kept the same way)". The parity-test claim is now true: d08c91f8e compares CHECKBOX_ATTRIBUTES too.
2. Summary, projection bullet: add that a raw-HTML checkbox is read as the allowlist keeps it, so it and its tick are not source_only (7731d0cc8), and that a tick beside a word edit in the same item keeps its word marks (1f6cb05a3).
3. "KPress 0.3.10" section: "writes its form's `<input>` as a disabled box, which the allowlist now keeps" is wrong. At 0.3.10 KPress removes that input (`<input name="q" src=...>` has no type, so it is not a checkbox) along with the `<link>`, before the allowlist sees either; the fixture diff deletes both, and the session hands them to the allowlist directly (`kpressRemoved`).
4. Known gap 1: KPress 0.3.10's components.css (installed copy, lines 1118-1191) adds structural rules for a class-free disabled checkbox that is the first child of a `.kpress-prose li` (or its first `p`), and its comment names Metabrowser's inert hardener as the case. So the native-checkbox-beside-a-bullet gap is probably closed for `ul` items. Not checked in Chrome at 0.3.10: re-run the headless-Chrome check and drop or rewrite the gap, or say it is unverified.
5. Test plan: the headless-Chrome item ran with KPress #82 overlaid before its release, before that CSS change; say it was not re-run at 0.3.10 (or re-run it). Add review A's tests: test_a_raw_checkbox_and_its_tick_are_changes_the_render_shows, test_a_raw_input_the_render_drops_is_flagged, test_a_tick_beside_a_word_edit_keeps_the_words_marked, the HOSTILE_README boxes, and the session's `boxes`.
6. Guided review: re-pin head to 96e13f0a51001af25a402a6d316650684fb21e28 and merge_base to 7c4bd886b3fbfa026e7187d621956805a25616d3 (the base moved). Item 1's note: drop "so the three tests the description says fail on 0.3.9 are expected to pass here" (the description no longer mentions them). Moved ranges: inert_html.py 57-62 -> 57-64, 187-192 -> 189-194, 208-213 -> 210-215, 490-494 -> 492-496, 652-653 -> 653-654, 703-708 -> 705-710, 844 -> 846; static/inert-html.js 11-16 unchanged (11-16), 127-132 -> 128-134, 148-154 -> 150-156, 417-424 -> 419-426, 626-634 -> 628-636, 729 -> 731; markdown_projection.py (shifted also by the base's _COMMENT change) 124-131 -> 125-132, 578-582 -> 587-591, 764-765 -> 784-785, 1221-1224 -> 1242-1245. New code worth an item or a reference: markdown_projection.py 658-661 (_RawMarkup docstring), 683-699 (handle_starttag: first-wins attributes, input through allowed_attributes), 1590-1599 (_inline_change attributes ignoring checked on an input). Item "Allowlist tests on both sides" should mention HOSTILE_README_BOXES and the session's `boxes`; item "Docs and changelog" should mention the raw-checkbox and word-mark sentences added to arch-diff-pipeline.md, reviewing-pull-requests.md and changelog.d/mb-rm6u.md, and SUPPLY-CHAIN-SECURITY.md's SHA-256 match.
