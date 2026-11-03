---
type: is
id: is-01m6f3dkmagq7az0j52zq4je42
title: "Keyboard: walking changed files jumps the diff to that file"
kind: task
status: in_progress
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f39zpnk9rc3kjy552b88qj
hold: null
hold_until: null
created_at: 2026-11-02T21:42:34.377Z
updated_at: 2026-11-03T07:36:49.231Z
started_at: 2026-11-03T06:46:33.001Z
---
The user, 2026-11-02: easy to scroll through files within a PR, and it may require rapid scrolling of the diff view to the relevant file when we navigate between files. Acceptance: changed-file rows are a Navigational Row Collection with the same contract as PR rows. Moving between files scrolls the diff straight to that file's bar, an immediate jump and not smooth scrolling, and focus stays in the nav. The file arrives hydrated even past MAX_HYDRATED_FILES, since builtin_plugins/diff/sidekick.py has a wanted_file path. Holding a key queues no request per row: latest wins, older ones cancelled. The position holds: neighbours hydrating above the target must not move it, and Back's history.state.pullPlace restore is kept. The selection follows a reader who scrolls the diff by hand, without stealing focus. It holds on the stress case, a real pull request of 1,183 files and +281,131 lines, so the tree stays bounded or virtualized; budgets come from the performance study. Pin in a browserless session with a golden, plus real-Chrome evidence for the scrolling.

## Notes

2026-11-03: from the diff view's owner, in the stack below at b29dc787 (#284 9b624b3a, review E1's mount fix): a ready file past the first screen is now drawn one or two frames after a jump, so scrollToFile's lines promise settles a little later and can come back superseded. Types unchanged; documented in docs/large-content-rendering.md. The walk must treat superseded as normal under a held key.

2026-11-03: step 4's scroll-follow ('the selection follows a reader who scrolls the diff by hand') depends on mb-6453 (under mb-2iok): the diff view reports the file whose bar or reserved block is at the top of the pane, drawn or not, without forcing a draw. mb-6453 waits for #284's mount change (mb-ivvw).

2026-11-03 HANDOFF: implemented on wip/pulls-4-files fff7d6a3, never run in a browser, budgets NOT measured. createFileTreeController.move walks the visible rows (folders and files), clamped. On a file it marks the row current, and when the page holds this pull request it calls page.fileForPath (a not_in_comparison row is muted) and then page.showFile on every key, with no debounce. The address is replaced only when the walk stops (FILE_WALK_SETTLE_MS 120 or key-up), with jumped:true, so the host moves only the address. When the page is another pull request's, a single press opens the file's address at once and a held key opens it when the walk stops. Click and Enter push. Back's pullPlace restore is kept: showFile does not override a place the entry saved. Not done: the selection following a reader's own scroll (needs a diff-view accessor for the file at the top; ask its owner). Candidates for the budget run, reachable in the list: astral-sh/ruff#29121 (1,627 files), #29817 (1,031); django/django#21728 (2,235).

2026-11-03, from #284's owner: the diff view's mount is changing (draw only the first screen's rows at mount; other ready files go through the deferred path with their patches in hand). Do not edit diff-view.js's mount or its deferred scheduler until they send the new head. The scrollToFile and fileForPath contract is meant to stay. Find in page will not reach undrawn rows, so the Pulls nav's jump to a file is how a reader reaches one: never rely on every file's rows being in the DOM; go through scrollToFile.

2026-11-03: contract from #284's addressed head, in the stack below at claude/v012-overlay-acquisition f7cf3464. fileForPath(path) answers typed kinds: {kind:'file', path, fileId, changeKind, availability}, {kind:'not_in_comparison', path, listTruncated}, or page-level {kind:'no_diff', path}; scrollToFile is unchanged. setTab('files') through the handle now moves the address, so Back behaves as after a click. The comparison address carries &store= from METABROWSER_SETTINGS.STORE_TAG beside &build= and is immutable only when both match; build any comparison URL through the diff view's prefetch builder, never by hand. Jump-scrolling may merge now: the gate is lifted.

2026-11-03: scrollToFile contract from PR #284 at 1251d874, may still change through its reviews; wait for the other session to send its addressed head before merging. The shell calls pullPageHost.page().scrollToFile(path), where path may be GitHub's filename, a rename's old path, or a deleted file's path. It answers synchronously: {kind:'jumped', fileId, path, availability, lines}, where lines resolves to painted, none, failed, or superseded; {kind:'not_in_comparison', path, listTruncated}, nothing moves; {kind:'no_diff', path}; {kind:'disposed', path}. fileForPath(path) asks without moving. From Conversation, call setTab('files') and then whenFilesReady(). Call it on every key repeat and do not debounce. Documented in docs/large-content-rendering.md and pinned by tests/dom/diff-file-jump-session.js. Also: the comparison route takes &build=, and Conversation prefetches Files changed through builtin_plugins/github/comparison-prefetch.js, so do not add a second fetch of the comparison. A very large list's mount is one long task of 262-628 ms; tell the other session before touching that. Base order: #280, #284, #283.

2026-11-02: budgets from the performance study, explorations/performance-loop/experiments/exp-040-files-changed-recomputes-the-whole-patch-per-request.md on origin/claude/v012-pr-review-perf at a377ef0a; read its jump section. Bar on screen within 50 ms; first lines within 150 ms for any file N; drift 0 px; key delivered at 33 ms per step (30 per second); at most 1 request in flight, the resting file; queue empty within 300 ms of key-up; no task over 50 ms. Do not drive jumps by scrolling to DOM you then hydrate: hydrating neighbours pushed the target 53,661 px off screen. Call the diff view's scrollToFile API being built on claude/v012-large-pr-perf, with target-first hydration, cancellation, and no drift, rather than reimplementing it. The other session sends its contract when it lands; do not merge jump-scrolling before then.
