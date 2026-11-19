---
type: is
id: is-01m7s7zhqth6z2pe1cc2xtf0w3
title: View on GitHub sits on the title's baseline on every view (file, folder, pull request, commit)
kind: task
status: in_progress
priority: 2
version: 6
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T06:30:22.713Z
updated_at: 2026-11-19T08:53:38.528Z
started_at: 2026-11-19T06:31:15.384Z
---
Owner, 2026-11-18, verbatim: "on the main file view, the up arrow can do without a box except on hover, like the collapse chevron. / also on the main file view that path, e.g. ~/wrk/github should be cleanly aligned with the main folder name, same baseline, same padding / also on that, the border below it should be the same and aligned with the border below the main folder name in the nav bar. / the other main page views for commits and PRs don't have a parent folder applicable so this i sjust skipped for these / for all, the View on GitHub button should be aligned with same baseline as the main title (large text filename, PR title, or commit title)". Then: "When done, the top bar should have the same rhythm on the nav panel and on the right, and the title and the Open View on GitHub buttons should all look the same and be aligned properly. The only difference will be that the file view has an extra section at the top for the parent folder." Done together with mb-48rf (nav path row padding) in one PR, branch claude/nav-root-padding.

## Notes

Compatibility with PR #602 (site-neutral web panes, session 'GitHub button browser display options'): #602 renames the View on GitHub links' markers to data-web-view=open/external, keeping the root's data-view-on-github. The header PR changes only the button's layout and styling (no markup, attributes, apps/macos or metab-contract.toml), selects by [data-view-on-github] or class, and whichever PR lands second merges main. Overlapping files: tests/dom/view-header-chrome.mjs, tests/dom/github-pull-header-chrome.mjs, docs/design-system.md.

PR #608 (branch claude/nav-root-padding). Baseline strut .view-header-end::before at the title's type, align-self: baseline; first-line float room in .view-header-title-group::before. Label baseline == title baseline: file/folder 72/72 (was 60 vs 26), commit/PR 38/38 (was 38 vs 26). Narrow mode: @container kpress-doc (width < 380px) moves a file's/folder's corner onto the eyebrow row (overflow-wrap breaks 'docs' mid-word beside a float); 380 = 2*padx + title font + gap + 2*room, pinned by test_the_corner_leaves_a_narrow_title_its_row. No markup change; #602 still open at PR time. Fragment changelog.d/mb-tatf.md.

Review A on #608 (A1, Medium), fixed in 14248fda0: threshold raised to @container kpress-doc (width < 680px) = 2*padx + title font + gap + corner-room (150) + new --view-header-title-room (450), derived by test_the_corner_leaves_a_narrow_title_its_row. 450 px holds 91% of this repository's 2,164 names at the title's type (p50 250, p90 424, p95 505). Chrome band checks: CONTRIBUTING.md (204.6 px) at 480 and arch-views-models-routes.md (318.8 px) at 560 on one line in narrow mode; the latter beside the room at 720. Residual, disclosed in the PR body and dispositions: a name wider than 450 px still breaks mid-word beside the room from 680 px to about its width + 230 px (505 px name: 680-735). Closing it needs a JS first-line check (ResizeObserver; move the corner when the title's unbroken width exceeds its first line beside the room); proposed, not done. Fragment updated.
