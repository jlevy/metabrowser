---
type: is
id: is-01m84jp3n8fvsryvh03cwc4388
title: "PR #745 merge with #751: the File type filter's facade drops a diff's sectionForPath and pathForSection, so a place in a filterable diff falls back to the pane's offset"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
created_at: 2026-11-23T16:09:06.471Z
updated_at: 2026-11-23T16:09:06.471Z
---
Found while merging main's File type filter (#751) into #745 (merge 6bd0e5031). The filter hands a host a facade over whichever diff it mounted, and lists the handle's methods; #745 added sectionForPath and pathForSection to the diff view's handle, which the pull request page keeps a reader's place in a file with. The facade did not pass them on, so on any filterable diff (more than one file) the page found no section and the place fell back to the pane's offset.

Fixed in 9ab02260b: the facade passes both to the diff mounted now, and a section of a replaced diff names no file. tests/dom/diff-type-filter-session.js fails without it ("facade.sectionForPath is not a function"). The commit and its source comments cited mb-owwk (A3 of review A), a different finding; review C's C3 on #745 asked for this bead, and the comments now cite it.

Review C: https://github.com/jlevy/metabrowser/pull/745#pullrequestreview-6024808335
