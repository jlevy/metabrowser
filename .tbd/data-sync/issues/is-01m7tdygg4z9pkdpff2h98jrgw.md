---
type: is
id: is-01m7tdygg4z9pkdpff2h98jrgw
title: "Mirror heading: drop the ref and commit beside the repository name; commit IDs take the size of the text around them"
kind: bug
status: in_progress
priority: 2
version: 5
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T17:33:54.562Z
updated_at: 2026-11-19T18:52:47.211Z
started_at: 2026-11-19T17:34:26.174Z
---
Owner, 2026-11-19, verbatim: "when I open a bare cloud repo the top level title of the repo now has a branch name and a hash right next to the title. These should not be there. They are clutter. Also, they're the wrong font size on the hash name, so there's some sort of design system inconsistency anyway we sholud make sure our design system always renders monospace hashes as the size of the fonts surrounding them. But in any case, these should not be showing anyway. The branch chooser below indicates the branch." Source: server.py _pin_label_html adds .header-revision .header-ref and .header-revision.git-commit-sha; styles.css .git-commit-sha has a fixed font-size var(--nav-font-size), with per-context overrides (.source-ref-selector, .source-freshness).

## Notes

PR #613 (branch claude/mirror-heading-name-only, head a521e17f2; CI run 44587991647 green 2026-11-19, 22 pass, stack-integration skipped as usual). A pin with a name is headed by the name alone: a served mirror (repository's name) and, per the coordinator's decision 2026-11-19, a checkout revision (folder's name); the ref selector names the ref and the tooltip the full commit. A pin with no mirror (in-process only; no ref selector) keeps ref + short commit. .header-ref removed; .header-revision and .header-path:has(> .header-revision) kept for the no-mirror pin. .git-commit-sha inherits its line's size with font-size-adjust: var(--font-sans-ex-height) (Clean 0.486, System 0.526, measured Chrome 152 2026-11-19; Menlo 0.547, SF Mono 0.526 from OS/2) and line-height: normal (timeline row 22 -> 21 px). Record: design-rule-measurements.md 'Short Commit IDs'. macOS app WebKit not measured. First head afee7c38b failed test_user_guides_name_no_tracker_ids (bead ID in docs/design-system.md); fixed in c2dff2e2a. afee7c38b's commit message lacks a blank line after its subject (not amended per no-amend rule).
