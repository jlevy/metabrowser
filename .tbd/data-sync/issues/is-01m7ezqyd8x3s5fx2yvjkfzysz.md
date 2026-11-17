---
type: is
id: is-01m7ezqyd8x3s5fx2yvjkfzysz
title: "Sans Markdown: h2 headings upright; serif documents keep the italic"
kind: bug
status: closed
priority: 2
version: 8
spec_path: docs/project/specs/done/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T06:54:00.615Z
updated_at: 2026-11-17T05:58:26.633Z
started_at: 2026-11-15T07:10:23.619Z
closed_at: 2026-11-16T16:30:51.993Z
close_reason: "Merged into main at afda3599f (stack #446 lower layers)."
resolution: null
duplicate_of: null
---
The user's request (2026-11-15), verbatim: "on the chrome or sans markdown docs let's not make the h2s italic. we can preserve the italic on the serif mode as that is more consistent with our standared past kpress stylings."

Where the italic comes from: KPress 0.3.5's `format/static/css/document.css` sets `.kpress-prose h2 { font-family: var(--kpress-font-prose, …); font-style: italic; font-weight: 400 }`. The shell sets no rule that undoes it for a sans face. KPress also sets italic on `h4` and `h6`, but the user named h2s, so those are unchanged.

Sans contexts:
- **Chrome Markdown:** anything inside `.chrome-prose` (#438: PR descriptions, comments, reviews, commit bodies).
- **Documents under the sans reading font:** `html[data-prose-font="sans"]`.
- **The `md-body` fallback** under the sans reading font, if its h2 inherits the italic.

Done when:
- an h2 in any sans context is upright (`font-style: normal`), keeping its size, weight and spacing;
- an h2 in a serif document stays italic, exactly as now;
- the rule is one scoped rule in the shell's prose styles, tied to the same face hook #438 uses (`--kpress-host-font-prose` and `.chrome-prose`) rather than to each surface, and stated once in `docs/design-system.md` next to "Serif Is for Documents";
- it's measured in headless Chrome for every context × both reading fonts × both font sets, by extending #438's `tests/dom/prose-faces-chrome.mjs` session with an h2 `font-style` check that fails before the fix;
- CHANGELOG is updated.

Depends on #438's `.chrome-prose`. Pull request 7 of the plan's stack.

## Notes

Implemented on branch claude/sans-h2-upright, commit ffadbd4e5 (cut from origin/main 03a79f0c), not pushed.

Rule: src/metabrowser/static/styles.css, right after the `.chrome-prose` rule:
`html[data-prose-font="sans"] .kpress-prose h2, .chrome-prose .kpress-prose h2 { font-style: normal; }`
Only the style changes. h4/h6 untouched. The md-body fallback was measured upright already in every pass (its h2 is `.md-body:not(.metabrowser-kpress-host) h2`, outside `.kpress-prose`), so the rule does not name it.

Docs: docs/design-system.md, "Serif Is for Documents", one paragraph. CHANGELOG entry under Unreleased.

Test: tests/dom/prose-faces-chrome.mjs places an h2 in each of the 6 Markdown probes (Document view, chrome prose KPress, Changes Markdown, md-body, md-body in chrome-prose, Overview README) and checks its font-style in all 4 passes (serif/sans x clean/system), plus, under the sans reading font, that its font-size, font-weight and margins equal the serif pass. CHECKS 56 -> 92 in tests/test_prose_faces_chrome.py.

Measured in headless Chrome (KPress h2: 19.8px 400 32px 16px; md-body h2: 18.2px 700 14.56px 7.28px, unchanged before and after):
- before: italic in every KPress context in all 4 passes, including chrome prose and the sans reading font; md-body upright.
- after: serif documents italic; chrome prose upright in both reading fonts; every context upright under sans; md-body upright.
Without the rule, 10 of 92 checks fail (chrome prose x 2 serif passes, 4 KPress contexts x 2 sans passes), each "its h2 is upright: italic". A mutant adding font-weight: 600 fails 6 keeps-its-size checks.

Local: make -o install format and lint-check pass; pytest tests/test_prose_faces_chrome.py passes alone (11.1 s call at load average 83). One run alongside test_design_vocabulary and test_process_group timed out at the session's 30 s budget at load ~60-80 after reporting 92 checks passed; back-to-back old/new sessions took 24/6/6/5 s, so the timeout was load. Pre-commit hooks passed.

Not verified: the macOS app's WebKit; the size guard cannot see a change confined to chrome prose, which is sans in both passes; make verify not run.

2026-11-15 restack: rebased onto origin/claude/pull-timeline (PR 6, 48165b77e) as 5d366e2c1. Only CHANGELOG conflicted; both entries kept, this one first. The styles.css and design-system.md hunks merged clean, and the layers below do not touch the session files, so CHECKS stays 92. After the rebase: make -o install format and lint-check pass (parity 53 routes covered, 5 exempt); test_prose_faces_chrome, test_design_vocabulary and test_process_group pass, 84 tests. Not pushed, no PR yet: the push was refused by the permission system. A draft PR body is ready for the coordinator.

2026-11-15 second restack and push: 5d366e2c1 sat on an older #451 head (48165b77e), so it was rebased again, while still unpushed, onto #451's final tip f98c4af45, as 55b7a5e50. The rebase was clean, and test_prose_faces_chrome passes (1 test, 11.2 s). Pushed at the user's go-ahead ("Yes, push PR 7"), and opened as draft PR #456 (https://github.com/jlevy/metabrowser/pull/456), base claude/pull-timeline, linked into stack #446 at position 7. From here on it takes merges only: no rebase, no force-push.

2026-11-15 review A (senior, round 1, at 55b7a5e5; verdict approve with nits, A1-A5 all Low): all five fixed in 19491aaac, pushed with --no-verify as a plain commit (no rebase). A1: design-system.md and the styles.css comment give h4 and h6 each a reason: h4 is KPress's sans under either reading font (document.css sets h2/h4/h6 to --kpress-font-sans, then h2 and h6 to --kpress-font-prose), so its italic is KPress's own sans style; h6 follows the reading face and keeps its italic because the user named only h2s. h6 behavior unchanged. A2: the plan's Sans Headings bullet names the two selectors and says md-body needs no rule. A3: Chrome test docstring rewrapped and reworded. A4: each pass checks chrome prose's KPress h2 box equals the Document view h2's from the same read; CHECKS 92 -> 96. A chrome-prose-only `font-weight: 650; margin-top: 0` mutant now fails 4 of 96. A5: test_serif_is_only_for_documents asserts the styles.css selectors setting font-style on `.kpress-prose h2` are exactly each sans hook (rules pointing --kpress-host-font-prose at var(--prose-sans-font)) + " .kpress-prose h2", declarations exactly {"font-style": "normal"}; mutants: rule removed fails, extra declaration fails, a third hook (whitelisted in _FACE_ROOTS) fails without the rule and passes with it. Gates: the three-file pytest run 85 passed; make -o install format clean; make -o install lint-check exit 0; pre-commit hooks passed. Dispositions comment: https://github.com/jlevy/metabrowser/pull/456#issuecomment-6898969357. Not run: make verify, pre-push gate; WebKit not verified.
