---
type: is
id: is-01m7s7g08bc2khyfmrdj5wkge7
title: "Short commit IDs: always 7 characters, monospace, one gray, as a design-system rule"
kind: task
status: closed
priority: 2
version: 7
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/604
    at: 2026-11-20T17:01:36.958Z
delegate: claude-code@spud10
labels:
  - linear
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T06:21:53.287Z
updated_at: 2026-11-20T18:01:28.622Z
started_at: 2026-11-19T06:22:17.348Z
closed_at: 2026-11-19T08:15:28.966Z
close_reason: "PR #604 merged"
resolution: null
duplicate_of: null
extensions:
  linear:
    id: 257ca12b-047a-482e-8912-d282f45cf529
    linked_at: 2026-11-20T18:01:28.620Z
---
Owner, 2026-11-18, verbatim: "let's make all short commits 7 chars, just like github. Make this part of the design system and apply it consistently. In the branch chooser, it's many more characters. They should always be monospace, always the same gray, and always 7 characters."

## Notes

PR #604 (branch claude/short-commit-ids-7). Round 1 head 27df8ea4e: SHORT_COMMIT_CHARS = 7 in src/metabrowser/commit_ids.py (short_commit), MetabrowserFormatters.shortCommit / metabrowser.shortCommit on the page, .git-commit-sha = --font-mono + --muted; applied to the chooser, heading, Commits tab, freshness, diff and pull plugins, CLI, version line, About box. Review A (1 High, 5 Low) addressed in cfdb3b159, origin/main merged at f04bd29a3: test_root_identity expectations from short_commit; uv-dynamic-versioning commit-length = 7; macOS records the full SHA, release check compares it whole, AppIdentity.shortCommitChars declared as a [[copy]] (App contract changelog entry); widened guards over src, tests, devtools, shell, Swift; pull timeline commit ID stays gray on hover (Chrome-checked); head-offer projection and _pin_label_html branches tested; stale types.d.ts and arch-views-models-routes text fixed. Dispositions: PR comment 7003121925. Local: lint-check, focused pytest (355 + 212 passed), affected goldens, Swift AppIdentity/DoctorReport/AppContract tests passed; full make macos-test not run (disk); test-scripts.sh quarantine-helper check fails locally, untouched by this PR.
