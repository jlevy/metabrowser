---
type: is
id: is-01m7hgsqvv3wbq4szbxd21sw49
title: "Native stack snapshot: a 304 page keeps its cached continuation even when its Link names a next page"
kind: bug
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
created_at: 2026-11-16T06:30:34.106Z
updated_at: 2026-11-20T17:11:18.446Z
---
From PR #471 Review A (A11) and Review B (refined fix): https://github.com/jlevy/metabrowser/pull/471#pullrequestreview-5915813181. src/metabrowser/builtin_plugins/github/pull_stacks.py:87-88 (StackPage docstring) and _page (:257-261): on a 304, a page keeps its cached has_next. GitHub's ETag covers the body only, and a 304 carries the Link header (probed by Review B against repos/cli/cli/labels). So a snapshot whose last page was full never asks for a page added after it, and still says complete. Fix as PR #471 did for the label set: take a 304's has_next from its Link when it carries one, keep the cached continuation only when it carries none, update StackPage's docstring, and add a small-page loop test. Belongs to the native stack layer, not PR #471.
