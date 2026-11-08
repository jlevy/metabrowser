---
type: is
id: is-01m6tkc0b7m61frpp1wv9cesms
title: Align PR author and opened-age metadata on one baseline
kind: bug
status: closed
priority: 2
version: 5
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-07T08:52:57.820Z
updated_at: 2026-11-08T02:41:40.415Z
started_at: 2026-11-07T08:56:38.990Z
closed_at: 2026-11-08T02:41:40.415Z
close_reason: Owning PRs are actually merged in native stack302 at main68534af933f0fcb38a5d81d62691bb42732d58ab, whose complete tree equals reviewed6cf001cdf and retains it in history. All28publishedheads were green with zero unresolved threads. Full gated6cf verification passed4916tests/9expectedskips,385goldens,audits and distribution; exact wheel installed and previews verified. Post-landing main verification and release preparation remain separate in mb-5k2w/mb-4bd2; no release tag or publication.
resolution: null
duplicate_of: null
---
User reports the PR header line jlevy opened 2d ago has inconsistent font sizes and baselines: the larger username does not sit on the same text baseline as opened/age. Use one metadata font size and line height across author, opened and age, with username emphasis by weight/color. Align text baselines while keeping the avatar optically centered and branch chips on their appropriate smaller scale. Scope styling to the shared PR identity component so other condensed age/nav text stays correct; verify real rendered browser geometry, wrap/narrow behavior, and normal font modes. Deliver as a focused stacked follow-up, document the design, and update the bead after review/verification.

## Notes

Owning PRs are actually merged in native stack302 at main68534af933f0fcb38a5d81d62691bb42732d58ab, whose complete tree equals reviewed6cf001cdf and retains it in history. All28publishedheads were green with zero unresolved threads. Full gated6cf verification passed4916tests/9expectedskips,385goldens,audits and distribution; exact wheel installed and previews verified. Post-landing main verification and release preparation remain separate in mb-5k2w/mb-4bd2; no release tag or publication.

Integrated donor6b16c847 by forward merge. Independent review passes; browser confirms PR main/card author14px bold, action/age14px and sharedbaseline; avatar centered independently. Compact row ages/chips retained. Final combined gate, PR/CI and installation pending.
