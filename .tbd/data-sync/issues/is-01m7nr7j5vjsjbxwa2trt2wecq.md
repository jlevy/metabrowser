---
type: is
id: is-01m7nr7j5vjsjbxwa2trt2wecq
title: "Untrusted inert renders: pass plain_code for pull request text and --untrusted folders"
kind: task
status: closed
priority: 3
version: 2
labels:
  - pulls
  - security
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-17T21:57:24.794Z
updated_at: 2026-11-18T02:29:12.857Z
closed_at: 2026-11-18T02:29:12.856Z
close_reason: "Done in PR #527: every inert render passes plain_code=True (review A17)."
resolution: null
duplicate_of: null
---
Follow-up from review A of jlevy/metabrowser#511 (View on branch), finding A7, outside that pull request's diff. It belongs with mb-273l and its pull request, #527, which change the untrusted render path.

Two inert renders still highlight fenced code whose highlighted output they then discard:

- A pull request's description, comments, and reviews: `builtin_plugins/github/pull_markdown.py` calls `kpress_adapter.render_kpress_view` without `plain_code`, and the inert rebuild drops every `class` the highlighter wrote. That text is written by anyone who can comment on the pull request.
- A folder served with `--untrusted`: `server.py`'s KPress render route renders under the folder's profile without `plain_code`, then runs `kpress_adapter.inert_render` when active content is off.

The reasoning beside `kpress_adapter._PLAIN_CODE` applies to both: a Pygments lexer can cost far more than its input's size (review G of #348), and the inert output shows a fence as plain text either way. Neither has been measured. Pass `plain_code=True` wherever the render is made inert, in #527 or separately, with a test that the render reaches no lexer, as `tests/test_git_revision_content_routes.py` has for a pin.
