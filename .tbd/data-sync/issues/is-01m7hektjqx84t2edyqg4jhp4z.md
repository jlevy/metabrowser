---
type: is
id: is-01m7hektjqx84t2edyqg4jhp4z
title: "Pulls toolbar: let Reload share the Show cluster's last line at a narrow pane"
kind: task
status: open
priority: 4
version: 2
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-16T05:52:23.126Z
updated_at: 2026-11-16T06:16:58.375Z
---
Follow-up from PR #458 review A (A4), https://github.com/jlevy/metabrowser/pull/458#pullrequestreview-5915435915. Where the Show group takes the cluster layout, Reload starts a line of its own, so the Pulls toolbar is three lines where two would fit (docs/design-system.md, Navigation Toolbars Wrap, 'Where it breaks', which now states the exception; tests/dom/nav-toolbar-wrap.mjs judge exempts it). Options: the cluster's chips as items of the row (display: contents on the radiogroup), which risks its accessibility semantics in WebKit; or flex: 1 1 0 on the cluster with align-self: flex-end on Reload, which the reviewer suggests but which needs measuring first in Chrome and WebKit. Waits on a decision whether the extra line is worth the change.
