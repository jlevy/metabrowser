---
type: is
id: is-01m84stcmgbetw71pc3bzxp8aw
title: "Rendered diff: show a file with a task list, its boxes' ticks as changes"
kind: task
status: in_progress
priority: 2
version: 9
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
refs:
  - kind: pr
    url: https://github.com/jlevy/kpress/pull/82
    at: 2026-11-23T22:02:38.657Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/771
    title: Rendered and the untrusted Document view draw task-list boxes
    at: 2026-11-23T23:47:29.708Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
hold: null
hold_until: null
created_at: 2026-11-23T18:13:46.765Z
updated_at: 2026-11-23T23:47:44.911Z
started_at: 2026-11-23T18:26:01.829Z
---
markdown_projection.py refuses any file with a task list (task_list), because KPress writes the checkbox as raw HTML and the inert render drops its checked state. Project the checkbox as an inert element that keeps its state, and count the state in the block's signature so ticking a box is a change.

## Notes

Blocked on KPress: native task-list tokens are in jlevy/kpress PR #82 (kpr-1m2b, CI green), and its release is tracked as kpr-nehd (0.3.10). Once released, bump kpress here and remove the task-list refusal in markdown_projection.py; the box's state is token.meta["checked"].

2026-11-23: implemented in PR https://github.com/jlevy/metabrowser/pull/771 (branch claude/task-list-boxes, on claude/diff-current-chooser, stack #770). The inert allowlist (inert_html.py, static/inert-html.js) keeps an input only as a task list's box: type="checkbox", always disabled, checked when the document's was (CHECKBOX_ATTRIBUTES). The projection reads KPress's kpress_task_checkbox token: one element of the tally, no part of the hidden signature, and a ballot box, ticked or not, in a block's words, so a tick is a change Rendered shows. No task-list detection, marker parsing, checkbox markup or styling in Metabrowser. The task-list refusal was already gone with mb-ueqx.

Tested with KPress #82 at b12f720 overlaid (uv run --with-editable on a clone in attic/): projection, inert HTML (Python and JS), docs discipline, the PR rendered golden, and end to end on a real metab server in headless Chrome (pull request 7's README.md ticks one box and unticks another; trusted and untrusted Document views).

Left for the pin bump after KPress 0.3.10 is released: kpress==0.3.10 in pyproject.toml; uv lock; the kpress date in uv.toml's exclude-newer-package; a SUPPLY-CHAIN-SECURITY.md row; re-record tests/fixtures/inert-html-kpress-tree.json and the session output in tests/golden/cli-ui-inert-markdown.tryscript.md; move the KPress version in the asset URLs of cli-github-pull-rendered.txt, cli-github-checkout.txt and cli-api-shell.tryscript.md. On 0.3.9 three tests fail until then: the tick test, the token test, the PR rendered golden.

KPress gaps found: (1) the item's and list's classes are token attrs, indistinguishable from attribute syntax, so an added task list or an item gaining a box reads source_only; (2) KPress's box CSS keys on li.kpress-task, which no inert surface keeps, so Rendered and the untrusted Document view show a native disabled checkbox beside a bullet; (3) sanitized mode writes every raw input, even type=text, as a disabled box.
