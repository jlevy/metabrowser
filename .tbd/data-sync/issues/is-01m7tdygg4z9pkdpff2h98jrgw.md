---
type: is
id: is-01m7tdygg4z9pkdpff2h98jrgw
title: "Mirror heading: drop the ref and commit beside the repository name; commit IDs take the size of the text around them"
kind: bug
status: in_progress
priority: 2
version: 4
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T17:33:54.562Z
updated_at: 2026-11-19T18:18:19.656Z
started_at: 2026-11-19T17:34:26.174Z
---
Owner, 2026-11-19, verbatim: "when I open a bare cloud repo the top level title of the repo now has a branch name and a hash right next to the title. These should not be there. They are clutter. Also, they're the wrong font size on the hash name, so there's some sort of design system inconsistency anyway we sholud make sure our design system always renders monospace hashes as the size of the fonts surrounding them. But in any case, these should not be showing anyway. The branch chooser below indicates the branch." Source: server.py _pin_label_html adds .header-revision .header-ref and .header-revision.git-commit-sha; styles.css .git-commit-sha has a fixed font-size var(--nav-font-size), with per-context overrides (.source-ref-selector, .source-freshness).

## Notes

PR #613 (branch claude/mirror-heading-name-only, head c2dff2e2a; CI run 44585209195 green 2026-11-19, stack-integration skipped as usual). Served mirror heading is the name alone; checkout revision and no-mirror pins keep ref + short commit (no-mirror pins have no ref selector; checkout revision shares the working tree's name). .git-commit-sha inherits its line's size with font-size-adjust: var(--font-sans-ex-height) (Clean 0.486, System 0.526, measured Chrome 152 2026-11-19; Menlo 0.547, SF Mono 0.526 from OS/2) and line-height: normal (timeline row 22 -> 21 px). Record: design-rule-measurements.md 'Short Commit IDs'. macOS app WebKit not measured. First head afee7c38b failed test_user_guides_name_no_tracker_ids (bead ID in docs/design-system.md); fixed in c2dff2e2a. afee7c38b's commit message lacks a blank line after its subject (not amended per no-amend rule).
