---
type: is
id: is-01m6thd591bhgt6vp9v5ve0326
title: Show PR stacks in a compact position menu
kind: feature
status: closed
priority: 2
version: 8
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6thmx3973vnsw532ya5nk4h
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
child_order_hints:
  - is-01m6tv7b3d98gs7rgkg4m5zg2v
hold: null
hold_until: null
created_at: 2026-11-07T08:18:38.496Z
updated_at: 2026-11-08T02:41:40.403Z
started_at: 2026-11-07T08:19:49.400Z
closed_at: 2026-11-08T02:41:40.403Z
close_reason: Owning PRs are actually merged in native stack302 at main68534af933f0fcb38a5d81d62691bb42732d58ab, whose complete tree equals reviewed6cf001cdf and retains it in history. All28publishedheads were green with zero unresolved threads. Full gated6cf verification passed4916tests/9expectedskips,385goldens,audits and distribution; exact wheel installed and previews verified. Post-landing main verification and release preparation remain separate in mb-5k2w/mb-4bd2; no release tag or publication.
resolution: null
duplicate_of: null
---
Replace the current stack toggle/link list with a GitHub-like papers-stack icon and current-position/total trigger such as 5/23. Clicking opens a menu listing every PR title, stack position, and PR number, with the current PR indicated and links retaining correct local/external navigation. Reuse the existing Lucide family if suitable; inspect the GitHub PR321 stack presentation as reference. Follow existing menu, keyboard, focus, dismissal, status icon, and responsive design conventions. Add focused behavior evidence, document the design, and deliver as its own stacked layer.

## Notes

Owning PRs are actually merged in native stack302 at main68534af933f0fcb38a5d81d62691bb42732d58ab, whose complete tree equals reviewed6cf001cdf and retains it in history. All28publishedheads were green with zero unresolved threads. Full gated6cf verification passed4916tests/9expectedskips,385goldens,audits and distribution; exact wheel installed and previews verified. Post-landing main verification and release preparation remain separate in mb-5k2w/mb-4bd2; no release tag or publication.

Real browser testing found that GitHub's native stack API supplies membership without titles. Fix8b7eabc8 projects titles from the matching source/reader catalog using indexed batches, while retaining the original membership-only cache schema. Title edits change the ETag without provider calls. Independent review passes. Tests cover1001members and identity isolation; the browser confirms all22 cached titles, current ordinal/number, and normal menu styling. Final full gate, publication, and CI are pending.

Realbrowserfoundnative/stacksAPIhasnotitles: correctedwith8b7eabc8 source+reader-matching catalogtitleprojection, indexed1000rowbatches with1001membertest, originalschema1membershipcache unchanged, titleeditschangeETagwithoutprovider. Existingtrustediconparserinvariantcorrectedandmenulinksstandardnonunderlined. Independentreviewpasses. Rootbrowserconfirmedall22titles/currentordinal/number andnormalmenuink. Fullgate/PR/CI pending.
