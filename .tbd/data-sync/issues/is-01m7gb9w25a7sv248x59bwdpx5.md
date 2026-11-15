---
type: is
id: is-01m7gb9w25a7sv248x59bwdpx5
title: "Titles: a conventional-commit prefix is regular weight and the rest bold, everywhere"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-15T19:35:16.804Z
updated_at: 2026-11-15T19:35:16.804Z
---
The user's request (2026-11-15), verbatim:

"let's add a small default formatting rule for PR and commit titles. if there is a prefix such as

feat(ledger): chart strategies, range bands and Extended default (valuation Phase 3, WIP)

then the prefix part "feat(ledger):" (including the colon and any parenthetical) should be regular weight but the rest should be boldface. Regular commit messages that don't match that regex should just be bold as usual. But conventional commits should follow the pattern. it should be active only if it's 16chars or less. This should be a consistently applied design system, i.e. anywhere it's a commit title or a PR title"

Done when:
- One shared pure function splits a title into a conventional-commit prefix and the rest. The prefix is a type, an optional parenthetical scope, an optional "!", and the colon, as in "feat(ledger):", "fix:" or "refactor(api)!:". It counts only when that prefix, including the parenthetical and colon, is 16 characters or fewer, and is followed by a space and a nonempty rest. Anything else is no prefix.
- Every surface that shows a commit title or a pull request title draws the prefix at regular weight and the rest bold. Titles with no prefix stay bold as usual. Each surface uses one shared class or helper, not its own markup or weights.
- Surfaces to cover: the Pulls nav rows, the PR page title, the stack menu's members, the Commits tab rows, the Conversation timeline's commit rows, Quick Search results, and any other place that shows one.
- A surface whose title is not bold today is reported, not silently changed.
- The split is pinned browserlessly with focused cases: prefixes of exactly 16 and 17 characters, a scope with spaces, "!", a missing space, an uppercase type, a merge commit, a revert. Chrome checks pin the computed weights on each surface.
- docs/design-system.md states the rule once, beside the bold PR numbers convention, and the CHANGELOG says so.
