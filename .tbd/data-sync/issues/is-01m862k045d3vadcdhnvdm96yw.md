---
type: is
id: is-01m862k045d3vadcdhnvdm96yw
title: Place the Files branch chip beside a separate revision chooser
kind: feature
status: in_progress
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-11-24T06:06:16.196Z
updated_at: 2026-11-24T06:28:20.432Z
---
Put the selected ref on its own row immediately below Files. Keep its chip clickable for the selected ref actions, and give the chevron next to it the separate job of choosing another branch or tag. Remove the duplicate branch action from folder details and preserve working tree, tags, pins and PR refs.

## Notes

Combined PR https://github.com/jlevy/metabrowser/pull/783 at 9606d576071785ab37544dd776cd20de733f6546. Independent exact review https://github.com/jlevy/metabrowser/pull/783#pullrequestreview-6034662701. All 182 integrated tests passed, including Chrome for the separate controls, Info contents, root types, layout and lists. Exact hosted verification 45340582061 and PR CI 45340552689 are pending.
