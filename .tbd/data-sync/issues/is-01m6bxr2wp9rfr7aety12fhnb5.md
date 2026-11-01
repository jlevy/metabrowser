---
type: is
id: is-01m6bxr2wp9rfr7aety12fhnb5
title: "Pull-request Markdown has no paragraph or list spacing: paragraphs run together and bullets sit on the card's edge"
kind: bug
status: open
priority: 2
version: 1
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-11-01T16:05:42.933Z
updated_at: 2026-11-01T16:05:42.933Z
---
Found 2026-11-01 reviewing main c934a0b4 on pallets/click#3866 and jlevy/metabrowser#268. Measured in the browser: .github-pull-markdown p has margin 0 and ul has padding-left 0 with list-style-position outside, so bullets hang outside the text box, because the shell's global reset applies and builtin_plugins/github/styles.css sets neither. The rendered text arrives wrapped as <div><div><p>, so the existing '> :first-child' and '> :last-child' trims reach only the wrapper. Every description and comment is affected. A regular Markdown file on the same server is spaced normally.
