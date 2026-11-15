---
type: is
id: is-01m7eyvhy1vxs5whqpby281x9j
title: "PR Conversation: commit rows match comments in size and spacing, joined by a timeline line"
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T06:38:30.336Z
updated_at: 2026-11-15T07:10:30.144Z
started_at: 2026-11-15T07:10:30.142Z
---
The user's request (2026-11-15), verbatim: "the lines ont he Conversation part of a PR rendering like this below are too small font, not enough space above them. see how github actually renders PRs e.g. https://github.com/jlevy/metabrowser/pull/438 and mnotice it creates a line joining the commits and the comments in a clearer way. And also, the font sizes should be more consistent. We shouldn't make the commits smaller just because they're commits on this page. They should be similar to comments in size and similarly consistently spaced, more like what GitHub does."

The example they pasted was a run of commit rows on a PR's Conversation tab. Each row is a commit subject, "committed 1d ago" and a short SHA link, for example "feat(ledger): add method cells to current estimates / committed 1d ago / ef48cd7".

On main:
- The PR page's Conversation timeline draws a commit event with `h("div", { class: "github-pull-commit" }, …)` in `builtin_plugins/github/pull-page.js` (around line 4628): a `.github-pull-commit-subject`, a `.github-pull-quiet` "committed <age>", and a `.github-pull-commit-id` SHA link.
- Its styles are in `builtin_plugins/github/styles.css` (around lines 313-340 and 488-500).
- Comments and reviews are drawn by `textBlock` (around lines 4830, 4864, 4978).

Done when:
- Commit rows use the same type scale as the timeline's comments and reviews, with no smaller size just because they're commits. The metadata ("committed 1d ago", the SHA) uses the same quiet treatment as a comment's metadata.
- Commits and comments are spaced consistently, with enough room above each commit row or run of commits.
- A timeline line runs down the Conversation tab, joining commits, comments and reviews, the way GitHub's pull request page does. Study https://github.com/jlevy/metabrowser/pull/438 for the pattern; take the structure, not GitHub's assets or brand.
- The rule is stated once in `docs/design-system.md`, using existing tokens.
- It's measured in headless Chrome on a real pull request with both commits and comments, with before and after screenshots, and pinned by a test (with a paint-exempt row and its evidence if the claim is only about paint).
- CHANGELOG is updated.

Pull request 6 of the plan's stack.
