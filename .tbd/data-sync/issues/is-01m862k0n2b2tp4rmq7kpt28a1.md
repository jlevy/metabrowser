---
type: is
id: is-01m862k0n2b2tp4rmq7kpt28a1
title: Use an info icon for the sidebar folder details menu
kind: task
status: in_progress
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-11-24T06:06:16.737Z
updated_at: 2026-11-24T06:28:21.071Z
---
Replace the root folder details trigger chevron with a minimal shared Info icon. Keep Home on the folder name, common menu dismissal and labeled link actions. Document how the Info button, ref chip and ref chooser differ.

## Notes

Combined PR https://github.com/jlevy/metabrowser/pull/783 at 9606d576071785ab37544dd776cd20de733f6546. Independent exact review https://github.com/jlevy/metabrowser/pull/783#pullrequestreview-6034662701. All 182 integrated tests passed, including Chrome for the separate controls, Info contents, root types, layout and lists. Exact hosted verification 45340582061 and PR CI 45340552689 are pending.
