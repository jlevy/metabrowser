---
type: is
id: is-01m6frzh3stte4sry5t7zqrvrr
title: Carry changed_files in the pull record, so a filling file list says N of M
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6f3a9djmnfvp42fmnwhwtr7
created_at: 2026-11-03T03:59:21.720Z
updated_at: 2026-11-03T03:59:21.720Z
---
The plan's Changed Files in a Row says a filling list shows N of M files where the record gives M (changed_files). PullRequest in pull_record.py has no changed_files today (nor additions/deletions), and the scrubbed fixture in tests/fixtures/github-pull/responses.json has none, so step 4's data half counts N files and pages read of the Link header's last page. Adding it is a PULL_RECORD_SCHEMA bump (2 to 3; cached records refetch, no migration), _pull in pulls.py reading changed_files, the fixture gaining the field, and regenerated pull transcripts and recordings (cli-github-pull*, github-pull-page-responses.json, github-pulls-panel-responses.json). Then pull_files_route.py adds expected from the record and pull-files-tree.js says N of M. Best done after #285's addressed head settles, since those recordings are being regenerated there.
