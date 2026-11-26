---
type: is
id: is-01m8cp5qa81nxgz1ecg9kggzx2
title: On a pinned revision, a branch link's tooltip says it opens the served working tree
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md
labels: []
dependencies: []
parent_id: is-01m8bat4973h1bjzvpkwd8qjdy
created_at: 2026-11-26T19:43:59.303Z
updated_at: 2026-11-26T19:43:59.303Z
---
static/repository-links.js: a github.com blob/tree link naming the served branch opens /view/ with localization 'working-tree' and the tooltip WORKING_TREE_TITLE ('Open the corresponding path in the currently served working tree.'), on a pinned revision too, where what is served is a commit of that branch, not a working tree. Seen in README rendering and, since mb-e2lo, in a rendered diff at the head (tests/golden/cli-ui-diff-markdown.tryscript.md). Decide the localization and wording for a pin (e.g. 'revision', or a tooltip naming the served commit), and keep the checkout's wording.
