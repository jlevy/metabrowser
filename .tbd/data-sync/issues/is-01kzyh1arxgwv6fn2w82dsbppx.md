---
type: is
id: is-01kzyh1arxgwv6fn2w82dsbppx
title: "PR #37 review F4: Make remaining-type sort comparator lawful"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - pr-review
  - pr-37
dependencies: []
parent_id: is-01kzyh19dnb273gz5mhw90bse3
created_at: 2026-08-13T21:39:15.868Z
updated_at: 2026-08-13T21:53:02.007Z
closed_at: 2026-08-13T21:53:02.006Z
close_reason: "Fixed: the Remaining types comparator now uses a reflexive boolean difference and a regression test pins the row last."
---
F4 Low at src/metabrowser/builtin_plugins/folder/file_type_summary_model.js:174. The comparator returns 1 for compare(a,a) when a is the Other row. Replace it with a reflexive/transitive ordering that keeps Other last.
