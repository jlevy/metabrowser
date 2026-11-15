---
type: is
id: is-01m7ezqyd8x3s5fx2yvjkfzysz
title: "Sans Markdown: h2 headings upright; serif documents keep the italic"
kind: bug
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T06:54:00.615Z
updated_at: 2026-11-15T07:20:55.516Z
started_at: 2026-11-15T07:10:23.619Z
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
