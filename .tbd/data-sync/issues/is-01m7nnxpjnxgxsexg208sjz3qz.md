---
type: is
id: is-01m7nnxpjnxgxsexg208sjz3qz
title: "GitHub URL gaps: /pull/N/files#diff-<hash> to a file, commit URL opens /commit/<sha>"
kind: task
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
hold: null
hold_until: null
created_at: 2026-11-17T21:17:04.469Z
updated_at: 2026-11-18T21:41:50.607Z
started_at: 2026-11-18T21:02:16.063Z
---
Phase 1. Map GitHub's per-file anchor (hash of the path) to /pull/<n>/files/<path>; open a commit selection at /commit/<sha> instead of /view/.

## Notes

2026-11-18, checked against main a1100bca6. Landed in jlevy/metabrowser#540: a commit URL opens at /commit/<full id> (cli/selection_href.py selection_view_href, format_commit_href) and the dry run reports that page. Remaining: /pull/N/files#diff-<hash> is still dropped; builtin_plugins/github/urls.py keeps only a line anchor, so the per-file anchor does not reach /pull/<n>/files/<path>.

2026-11-18: the anchor is in jlevy/metabrowser#574 (branch claude/github-url-gaps). The reducer keeps diff-<64 hex>[line] as RepositorySelection.pull_file; builtin_plugins/github/pull_file_anchor.py names the file offline from the cached pull-files list, then the record's comparison, and the URL serves /pull/<n>/files/<path> or the Changes tab with a reason (file_not_changed, file_not_listed, files_unknown). metab reports file: and diff_line:; --present --dry-run reports page null and hands the anchor on. Goldens: cli-github-pull-file-anchor.txt, cli-present.tryscript.md; parity rows github.pull-file-anchor and app.present-pull-file-anchor. Not done: scrolling the Changes view to the anchored line (no per-line address in the diff view); #diff- anchors on commit pages; GitHub's old 32-hex anchors.
