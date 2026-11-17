---
type: is
id: is-01m7kagwjbznvzezsjazjrkeg4
title: "Font sizes follow one type scale by role: secondary metadata (ages, 'Updated just now', 'Fetched just now via GitHub CLI', counts) is one size everywhere unless a stated reason differs; main-view metadata at the body size"
kind: task
status: in_progress
priority: 1
version: 28
delegate: claude-code@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m7ks83f0r22b69d8arm28fkx
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
child_order_hints:
  - is-01m7knncamadmffy5yjsf0gbze
  - is-01m7knnd47bdeg6kqf685sbxd0
  - is-01m7knndr4gwwctymx3ss3hc6y
  - is-01m7knneap5591b7gje74bdk58
  - is-01m7knnexw917bbydftf1zxznk
  - is-01m7knng6vrg5gj2ckwgr083ts
  - is-01m7knngppd8e7a49m8jqct29p
  - is-01m7knnh7pdj941gf02athd4mp
  - is-01m7knnhq394xg507n8gktkrwc
  - is-01m7knnj87dw3qwnhyq3kyksfv
  - is-01m7knnjw9j03r00es4ba7acrt
  - is-01m7knnkcs48j27bbpekgqnp5s
  - is-01m7knnkwk9rvm4cr5p9b7q094
  - is-01m7kvjqavqcm7k9esjmhmygvz
  - is-01m7kvjqsrp983e03d768hbhsh
  - is-01m7kvjr783f02ar87xjrh1h1g
  - is-01m7kvjrm75qhbd7swqpv575cj
  - is-01m7kvjs1rmdrr1v16zp5tjt6v
  - is-01m7kvjsgqaf23b9zz1mn08hgb
  - is-01m7kvjsxs1s725a47p0hft122
hold: null
hold_until: null
created_at: 2026-11-16T23:19:21.413Z
updated_at: 2026-11-17T04:18:23.915Z
started_at: 2026-11-16T23:20:08.996Z
---
Owner, 2026-11-16: 'review font size for consistency in our design system. "Updated just now" on the nav panel in PR tab is larger than "Fetched just now via GitHub CLI" in the PR main body. Things like update time and less important metadata like that should all be the same size unless there's a specific reason to make it larger or smaller. Probably the small font size on the main view should actually be the regular body size. The diff summary text on the toggle is also too small, at least in the current version I'm seeing right now.' Stacked on #487 (header parity), which already moves the PR page's status line and the Diff summary to the body size.

## Notes

2026-11-17 handoff: PR #493 (claude/type-scale-by-role) review A published (A1 High = owner decision: file/folder header to 14 px; diff file bar follows; nav stays 13 px). Fix round pushed 71a22ffda, CI running; disposition reply not yet posted. Needs: reply, green CI, merge.

2026-11-17: fix round pushed at 71a22ffda; agent stopped while re-running touched Chrome checks; reply not posted. Handoff in PR #497.

2026-11-17 (2): main merged at 7778ccf51 for #495 golden; reply drafted in type-scale attic/inv/dispositions-A.txt, not posted. Handoff PR #497.

2026-11-17 (3): review A dispositions posted (issuecomment-6937738337) at head 00b3cc68f. Every finding A1-A13 checked against the code: all fixed or applied in 71a22ffda (A1, A2, A3 substantive CSS/test changes); 00b3cc68f adds two wording fixes (A1 breadcrumb comment mixed 13 and 14 px measurements; A5 Controls row "chips and their counts" contradicted the Micro row's count badge). Nothing deferred; child beads mb-h3mw..mb-966p already closed. Extension beyond the owner's three named decisions: a commit's files outside the served folder (.git-commit-file) also moved to 14 px as main-view path rows. Local: lint-check pass, focused pytest 264 pass; 57 browserless files 1357 pass, 1 root-only failure (test_github_pull_files_tree_session cache_unwritable, chmod ignored by root). CI at 71a22ffda passed all Chrome checks; its only failure was the stack-lines golden fixed by #495. CI for 00b3cc68f pending. PR body updated (Changes/Checks sections were stale after the round). Needs: green CI, merge.

2026-11-17 (4): review B (5932595696, follow-up, B1-B7 all Low) addressed in 5bcbbc4bc; dispositions issuecomment-6938160551. All fixed. B2 was a real 0.5 px offset: View file's link form inherited the bar's 1.5 line height; .diff-file-view now sets line-height normal (measured in headless Chrome 153 at DPR 1 and 2: both forms on the path baseline, bar 24 px). Beads mb-557i mb-046i mb-9vq0 mb-11nd mb-q39v mb-nxyu mb-fgx1 created and closed. CI at 00b3cc68f green; 5bcbbc4bc pending. Main not merged (waiting on #494 per coordinator).
