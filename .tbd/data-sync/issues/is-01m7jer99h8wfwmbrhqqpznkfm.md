---
type: is
id: is-01m7jer99h8wfwmbrhqqpznkfm
title: Extend the document-path check to tests/ and devtools/, narrowly
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-16T15:14:03.696Z
updated_at: 2026-11-16T15:14:03.696Z
---
test_document_paths_in_source_resolve (tests/test_docs_discipline.py:452-455) scans only src/ and apps/. PR #452 repointed about 20 document references in tests/ and devtools/ by hand. Running _document_path_findings over those trees finds about 490 example-path hits from fixtures, so a useful version checks only paths under docs/ or explorations/, record-shaped names, and quoted titles; it should also parse the title-before-path form ('"Idle Work" in docs/...', e.g. static/perf.js:905). From PR #452 review A9: https://github.com/jlevy/metabrowser/pull/452#pullrequestreview-5922214786
