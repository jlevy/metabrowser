---
type: is
id: is-01m839z1p2d8zv8x6hjt31rh0w
title: "T9: A Docs tab on the pull request page: its documents, rendered and expanded"
kind: feature
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10
labels:
  - diff
  - github
dependencies: []
parent_id: is-01m83968ry3rs287s3mgg0r93y
hold: null
hold_until: null
created_at: 2026-11-23T04:17:27.694Z
updated_at: 2026-11-23T07:54:15.893Z
started_at: 2026-11-23T07:53:37.929Z
---
Requested by the user 2026-11-22. A shortcut built on the diff File type filter: a new
second tab on the pull request page, **Docs**, between Conversation and Changes
(`PULL_TABS` / `TABS` in `builtin_plugins/github/pull-page.js`), showing only the pull
request's documents so a reader can read them quickly.

- **Membership:** the comparison narrowed to the registry's documentation group
  (`recommended-file-types.toml`: markdown, plain-text, restructured-text, asciidoc,
  org, pdf, word, rich-text, open-document, epub). Ask through T2's narrowing, either
  as that group's preset tokens in `types=` or as a `group=type:<id>` parameter in
  `tree_groups.py`'s vocabulary (`TreeFilter.group` is the precedent); pick one and pin
  it in a golden. No File type chooser on this tab: its filter is fixed.
- **Presentation:** the same diff visualization as the Changes tab (`mountDiffView`),
  but each document opens in its Rendered view by default (`diff-markdown.js`'s
  Rendered, with its change marks, deletions in red), and fully expanded: every file
  section open and no folded context. A format with no rendered projection shows its
  text diff unfolded; a binary document (PDF, Word) shows its labeled availability
  state.
- **Empty:** a pull request with no documents says so on the tab, with a link to
  Changes. Whether the tab shows at all when there are none is a decision to make
  with the user.
- **Key:** a free letter from the tab's label, chosen by the rule in the `PULL_TABS`
  comment and `docs/design-system.md` "Keyboard Shortcuts"; `tests/test_keymap.py`
  pins it.
- **Prefetch:** the Docs answer joins `comparison-prefetch.js` like the Changes tab's,
  so switching to it is instant.
- **Parity:** extend the PR page's tab session and golden
  (`cli-ui-github-pull-page.tryscript.md`), the route golden for the narrowed answer,
  and the parity registry; changelog fragment.
- **Delivery:** its own pull request, stacked on the diff File type filter's stack once
  the basic chooser works.

## Notes

Decision taken unattended (2026-11-22, user said not to ask): the Docs tab is always shown, keyed D, with an empty state linking to Changes when the PR has no documents, so the tab set and its keys stay stable from PR to PR. Revisit in the morning if the user prefers hiding it.
