---
type: is
id: is-01m7f6redchw2rrzg2jjzdw7c5
title: A server-written display for File Diff Format paths, in place of the browser's copy of the rule
kind: task
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
created_at: 2026-11-15T08:56:37.035Z
updated_at: 2026-11-20T17:11:21.422Z
---
Review A of #448 (https://github.com/jlevy/metabrowser/pull/448#pullrequestreview-5909894490), "Design Assessment", names the weakest part of the Diff summary: `displayPath` in `static/changed-files-tree.js` is a second implementation of the server's path display rule (`display_path` over `display_segment` in `invisible_chars.py`), a security-relevant rule kept in step by `tests/test_changed_files_display.py`, a parity test over chosen inputs (26,123 names).

The review's alternative: the server writes a `display` beside `path` on each File Diff Format side, as the `pull-files` route already does for GitHub's list. That would:
- remove the browser's copy of the rule;
- give the Diff summary's rows and the diff's file bars a display from the server;
- let the parity test go.

It costs a schema change across both implementations (the Pydantic model and `diff-model.js`'s validator) and the conformance corpus, and every adapter writing the field.

Not done in #448 by the coordinator's decision; filed at priority 3.
