---
type: is
id: is-01m7dm3bzsnq82ntn1atmvvt72
title: "Sans-serif Markdown: consistent space above and below headings"
kind: bug
status: in_progress
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-14T18:11:17.624Z
updated_at: 2026-11-14T18:40:42.146Z
---
The user (2026-11-14): "For formatted Markdown content that is sans-serif like PR descriptions the padding around h2s and at the top of the text is inconsistent, especially around h2s at the top of a section, there is too little space above the h2s. Let's understand why their spacing seems inconsistent and try to be as simple as possible without any hacks. Make sure that there's appropriate space above headers when blocks of text appear like this, and below headers. Make sure that the spacing is relatively consistent with the serif, but that we depart where necessary when it comes to more Chrome-like text (like PR descriptions or any areas where we are using sans-serif-formatted Markdown)."

Done when the cause of the inconsistency is explained (margin collapsing, a first-child rule, a section wrapper, or KPress defaults), headings in sans-serif Markdown have consistent space above and below (including a heading at the top of a section and after a block of text), measured in Chrome and WebKit, the rule is one simple CSS change consistent with the serif document scale except where sans needs its own values, the design system documents it, and a test pins it.

## Notes

PR #432 (head 6790a37b): cause was the PR text card's 8 px block padding (a header row's) combined with the first-child margin trim, which left an opening h1/h2 with 8 px above and 16 px below; heading margins inside texts already match the document scale in both engines. Fix: .github-pull-text block padding = --content-padding-y (16 px). Tests: test_a_heading_is_nearer_its_section_than_what_precedes_it (browserless) and tests/test_github_pull_text_chrome.py (Chrome, 52 checks). Found the empty-paragraph-before-heading bug, filed as mb-a9be. Review A (senior) running.
