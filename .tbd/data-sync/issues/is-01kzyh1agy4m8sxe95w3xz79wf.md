---
type: is
id: is-01kzyh1agy4m8sxe95w3xz79wf
title: "PR #37 review F3: Represent failed index state honestly"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - pr-review
  - pr-37
dependencies: []
parent_id: is-01kzyh19dnb273gz5mhw90bse3
created_at: 2026-08-13T21:39:15.613Z
updated_at: 2026-08-13T21:53:01.786Z
closed_at: 2026-08-13T21:53:01.785Z
close_reason: "Fixed: scanning now matches only the real scanning status, and failed indexing has distinct terminal copy with and without partial totals."
---
F3 Medium at src/metabrowser/builtin_plugins/folder/file_type_summary_model.js:200 and distribution_view.js:141. The scanning flag recognizes a nonexistent complete status and mislabels failed indexing as ongoing scanning. Use the real status vocabulary and render a distinct failed status.
