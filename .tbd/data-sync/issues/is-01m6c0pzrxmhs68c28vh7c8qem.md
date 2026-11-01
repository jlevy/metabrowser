---
type: is
id: is-01m6c0pzrxmhs68c28vh7c8qem
title: A file-level review comment reads as a line comment at path:1
kind: bug
status: open
priority: 4
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-11-01T16:57:32.701Z
updated_at: 2026-11-01T16:57:32.701Z
---
Found 2026-11-01 while working on PR #273. A sample of 3,181 recent GitHub review comments across 11 repositories had 37 file-level comments (subject_type: file), all with a numeric line, usually 1, and an empty diff_hunk. So the pull-request page shows them as path:1 linking to #L1 with no hunk. An empty hunk does not identify them, since 64 line comments in the sample also have one; telling them apart needs subject_type in the pull record, which is a record schema change. Low priority: the text and the file are correct, only the line is misleading.
