---
type: is
id: is-01m7f5ex295gdhxggbr3nsywcd
title: KPress styles every details in a .kpress article as a disclosure box; scope it to authored prose
kind: task
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7wysdnvzch4gb5zvqwvn04e
created_at: 2026-11-15T08:33:55.785Z
updated_at: 2026-11-20T17:14:44.604Z
---
Raised in the Design Assessment of review A on PR #447 (https://github.com/jlevy/metabrowser/pull/447#pullrequestreview-5909858397).

KPress 0.3.5's `document.css` styles every `<details>` and `<summary>` inside any `.kpress` article as a disclosure box: `.kpress details` sets a 1px border, a 0.75rem block margin, a sans face, `font-feature-settings` and colour; `.kpress summary` sets the caps label and chevron; `.kpress summary:hover` sets a hover colour; and `.kpress details[open] summary` draws a rule under an open summary. Any host element that is a `<details>` inside a KPress article inherits all of that.

Metabrowser now overrides it in three places:
- `builtin_plugins/diff/styles.css`, the rendered Markdown diff's fold of unchanged blocks (mb-m5dd, #447);
- `static/styles.css`, the shell's document disclosure label and chevron rules (around lines 4303-4316 and 4396-4415 at #447's head).

Idea: KPress scopes its disclosure styling to authored prose (for example the `<details>` a document writes, inside `.kpress-prose`), so a host's own `<details>` placed in a KPress article is not given a box. That would retire the host overrides.

This is a change in KPress, a separate first-party repository; nothing in KPress was changed for #447. Done when: KPress's disclosure rules no longer reach a host `<details>` outside authored prose, a KPress release with that change is adopted here, and the host overrides that only undo KPress's box are removed with tests/test_diff_markdown_fold_chrome.py still passing.
