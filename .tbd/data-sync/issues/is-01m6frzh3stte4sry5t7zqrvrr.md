---
type: is
id: is-01m6frzh3stte4sry5t7zqrvrr
title: Carry changed_files in the pull record, so a filling file list says N of M
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6f39t9zax1nbajkkasya6st
created_at: 2026-11-03T03:59:21.720Z
updated_at: 2026-11-14T18:44:32.722Z
---
The Pulls plan's Changed Files in a Row wants a filling list to show N of M files, with M from the record. PullRequest in builtin_plugins/github/pull_record.py has no changed_files (nor additions or deletions; PULL_RECORD_SCHEMA is 2), and the scrubbed fixture tests/fixtures/github-pull/responses.json has none, so the tree says N files with the pages read of the Link header's last page (describeFileList and initialExpansion in pull-files-tree.js). Adding it is a PULL_RECORD_SCHEMA bump to 3 (cached records refetch, no migration), _pull in pulls.py reading changed_files, the fixture gaining the field, and regenerated pull transcripts and recordings (tests/golden/cli-github-pull*, tests/fixtures/github-pull-page-responses.json, tests/fixtures/github-pulls-panel-responses.json). Then pull_files_route.py adds expected from the record, and pull-files-tree.js says N of M and sizes initialExpansion from it. The catalog's GraphQL rows (pull_catalog.py) could carry changedFiles as another source of M; they do not request it today.

## Notes

2026-11-03 HANDOFF: not started in this half. The tree still says N files with pages read of the Link header's last page (describeFileList, describeFileTree).
