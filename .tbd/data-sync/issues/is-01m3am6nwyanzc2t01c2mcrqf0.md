---
type: is
id: is-01m3am6nwyanzc2t01c2mcrqf0
title: A pasted GitHub URL with a raw Unicode character or space is refused without a recovery hint
kind: bug
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-09-24T21:12:35.485Z
updated_at: 2026-09-24T21:28:20.258Z
started_at: 2026-09-24T21:28:20.257Z
---
Found during the v0.12 alpha acceptance (mb-gnr9) on the integrated stack (PR #241; installed wheel 0.11.1.dev400+250a10c4).

A GitHub URL whose path holds a raw non-ASCII character or a space is refused with a typed error that says what is wrong but not how to recover:

```
$ metab 'https://github.com/jlevy/metabrowser/blob/codex/v012-markdown-anchors/tests/fixtures/github-markdown-repo/docs/雪.md'
Error: invalid ROOT (non_ascii): the URL contains a character outside ASCII
$ metab 'https://github.com/jlevy/metabrowser/blob/main/tests/fixtures/github-markdown-repo/docs/space name.md'
Error: invalid ROOT (control_or_whitespace): the URL contains a control character or space
```

The percent-encoded forms (`.../docs/%E9%9B%AA.md`, `.../docs/space%20name.md`) open correctly, pinned to the right commit and path. Users paste the decoded form: some browsers display and copy it, and it is what a person types. Other refusals from the same reducer name the shape and offer a URL to open instead (for example, `unsupported_github_url` offers the repository URL). Alpha matrix M02 requires that "rejected addresses have a recoverable explanation".

Acceptance test: extend the network-free GitHub URL golden (`tests/golden/cli-github-urls.tryscript.md` or `tests/test_cli_github_url_golden.py`) with a raw Unicode path and a path with a space. Either they are accepted and opened as their percent-encoded equivalents, or the typed error keeps its code and prints the percent-encoded URL to use. Control characters and credentials stay refused as they are.

Owning PR: #231 (GitHub URL open).
