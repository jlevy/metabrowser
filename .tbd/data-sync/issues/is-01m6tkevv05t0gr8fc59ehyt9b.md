---
type: is
id: is-01m6tkevv05t0gr8fc59ehyt9b
title: Unify commit and PR description surface styling
kind: bug
status: closed
priority: 2
version: 7
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-07T08:54:31.519Z
updated_at: 2026-11-08T02:41:40.424Z
started_at: 2026-11-07T08:56:39.004Z
closed_at: 2026-11-08T02:41:40.424Z
close_reason: Owning PRs are actually merged in native stack302 at main68534af933f0fcb38a5d81d62691bb42732d58ab, whose complete tree equals reviewed6cf001cdf and retains it in history. All28publishedheads were green with zero unresolved threads. Full gated6cf verification passed4916tests/9expectedskips,385goldens,audits and distribution; exact wheel installed and previews verified. Post-landing main verification and release preparation remain separate in mb-5k2w/mb-4bd2; no release tag or publication.
resolution: null
duplicate_of: null
---
User reports some commit description boxes have a gray/code-like background instead of the PR design. Apply the shared description surface treatment: subtle box, normal text color and sans-serif typography. Keep layout and design consistent across commit pages, PR pages and file rendering, reusing existing design tokens/primitives and their shared headers/gutters/reading widths. Preserve actual code and diffs as code, scoped typography, Markdown structure and narrow-screen behavior. Review the common components and update design documentation, focused existing checks and browser evidence before a stacked follow-up.

## Notes

Owning PRs are actually merged in native stack302 at main68534af933f0fcb38a5d81d62691bb42732d58ab, whose complete tree equals reviewed6cf001cdf and retains it in history. All28publishedheads were green with zero unresolved threads. Full gated6cf verification passed4916tests/9expectedskips,385goldens,audits and distribution; exact wheel installed and previews verified. Post-landing main verification and release preparation remain separate in mb-5k2w/mb-4bd2; no release tag or publication.

The latest shared-design request is covered with gutter beadmb-3vvt and baseline beadmb-ba73. Commit/PR messages share the neutral page-card,15px sans prose,22.5px line height, configurable reading measure, and24px outer pane gutter. Documents retain KPress's responsive inner padding and chosen reading face; source/diff content retains code typography and insets. The design system, current plans, and concise e2e playbook are updated and independently reviewed. Real checkout and managed pages are checked. Final full gate, publication, and CI are pending.

Integrated donor1d5f116d by forward merge. Independent review and94focused checks pass. Real commit0487921d browser confirms neutral page-card/regulartext15px sans22.5px lineheight, authored newlines, shared687px readingcard andx323.99 paneedge matching PRcard. Source/diff spacing untouched. Updated design/e2e/changelog; final combined gate, PR/CI and installation pending.
