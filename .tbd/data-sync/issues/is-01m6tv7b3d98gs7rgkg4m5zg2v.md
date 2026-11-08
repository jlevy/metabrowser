---
type: is
id: is-01m6tv7b3d98gs7rgkg4m5zg2v
title: Restore focus when choosing a PR stack member
kind: task
status: closed
priority: 2
version: 5
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6thd591bhgt6vp9v5ve0326
hold: null
hold_until: null
created_at: 2026-11-07T11:10:13.612Z
updated_at: 2026-11-08T02:41:40.447Z
started_at: 2026-11-07T11:10:14.086Z
closed_at: 2026-11-08T02:41:40.447Z
close_reason: Owning PRs are actually merged in native stack302 at main68534af933f0fcb38a5d81d62691bb42732d58ab, whose complete tree equals reviewed6cf001cdf and retains it in history. All28publishedheads were green with zero unresolved threads. Full gated6cf verification passed4916tests/9expectedskips,385goldens,audits and distribution; exact wheel installed and previews verified. Post-landing main verification and release preparation remain separate in mb-5k2w/mb-4bd2; no release tag or publication.
resolution: null
duplicate_of: null
---
Review of public pull request325 found keyboard focus can remain in the menu when it becomes hidden. Restore focus to a stable visible control/page destination without scrolling, and pin actual keyboard selection in the existing mount session. Evaluate the title-projection cost with evidence; missing titles array feedback is a same-build contract false positive because the server always emits aligned null fallbacks. No compatibility shim.

## Notes

Owning PRs are actually merged in native stack302 at main68534af933f0fcb38a5d81d62691bb42732d58ab, whose complete tree equals reviewed6cf001cdf and retains it in history. All28publishedheads were green with zero unresolved threads. Full gated6cf verification passed4916tests/9expectedskips,385goldens,audits and distribution; exact wheel installed and previews verified. Post-landing main verification and release preparation remain separate in mb-5k2w/mb-4bd2; no release tag or publication.

Menu3097cb7b integrated into325layer and cascaded forward. Capturephase closesmenu and restoresfocused visibletrigger before targetnavigation, without scroll/outsidefocussteal; keyboard/native modifierpaths pinned inexistingmountgolden. Requiredtitlesarray feedback rebutted as paired same-build contract. Titleprojection measured offloop bounded; no unproven optimization. Combinedfocusedgate passes; fullgate/newheadCI/publicdispositions pending.
