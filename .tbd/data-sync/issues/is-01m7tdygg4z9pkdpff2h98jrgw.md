---
type: is
id: is-01m7tdygg4z9pkdpff2h98jrgw
title: "Mirror heading: drop the ref and commit beside the repository name; commit IDs take the size of the text around them"
kind: bug
status: in_progress
priority: 2
version: 6
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T17:33:54.562Z
updated_at: 2026-11-19T19:10:18.142Z
started_at: 2026-11-19T17:34:26.174Z
---
Owner, 2026-11-19, verbatim: "when I open a bare cloud repo the top level title of the repo now has a branch name and a hash right next to the title. These should not be there. They are clutter. Also, they're the wrong font size on the hash name, so there's some sort of design system inconsistency anyway we sholud make sure our design system always renders monospace hashes as the size of the fonts surrounding them. But in any case, these should not be showing anyway. The branch chooser below indicates the branch." Source: server.py _pin_label_html adds .header-revision .header-ref and .header-revision.git-commit-sha; styles.css .git-commit-sha has a fixed font-size var(--nav-font-size), with per-context overrides (.source-ref-selector, .source-freshness).

## Notes

PR #613 (branch claude/mirror-heading-name-only, head aee37ba39, folding review A; previous head a521e17f2 had CI run 44587991647 green). Review A (senior r1): approve, 0 High/Medium, 5 Low; A1, A2, A4, A5 fixed in aee37ba39, A3 (System-font check in type-scale-chrome.mjs) deferred to a bead the coordinator will name; dispositions posted as PR comment 7019362309. A pin with a name is headed by the name alone: a served mirror (repository's name) and, per the coordinator's decision 2026-11-19, a checkout revision (folder's name); the ref selector names the ref and the tooltip the full commit. A pin with no mirror (in-process only; no ref selector) keeps ref + short commit. .header-ref removed; .header-revision and .header-path:has(> .header-revision) kept for the no-mirror pin. .git-commit-sha inherits its line's size with font-size-adjust: var(--font-sans-ex-height) (Clean 0.486, System 0.526, measured Chrome 152 2026-11-19; Menlo 0.547; SF Mono 0.530 in a WKWebView per review A, 0.526 OS/2) and line-height: normal (timeline row 22 -> 21 px). test_short_commit loops over server._FONT_SETS. Record: design-rule-measurements.md 'Short Commit IDs'. First head afee7c38b failed test_user_guides_name_no_tracker_ids; fixed in c2dff2e2a. afee7c38b's commit message lacks a blank line after its subject (not amended per no-amend rule).
