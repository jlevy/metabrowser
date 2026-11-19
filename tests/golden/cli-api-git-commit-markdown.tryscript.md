---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
  GIT_CONFIG_GLOBAL: "/dev/null"
  GIT_CONFIG_SYSTEM: "/dev/null"
  GIT_AUTHOR_NAME: "Test"
  GIT_AUTHOR_EMAIL: "test@example.com"
  GIT_COMMITTER_NAME: "Test"
  GIT_COMMITTER_EMAIL: "test@example.com"
  GIT_AUTHOR_DATE: "2020-01-01T00:00:00Z"
  GIT_COMMITTER_DATE: "2020-01-01T00:00:00Z"
before: >-
  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_PREFIX GIT_NAMESPACE GIT_CEILING_DIRECTORIES &&
  mkdir -p gitroot &&
  cd gitroot &&
  git init -q --initial-branch=main . &&
  printf '# Repo\n' > README.md &&
  git add README.md &&
  printf '%s\n'
  'feat: teach the app to count'
  ''
  'The app counted to one. This change wraps its prose at seventy-two'
  'columns, as a commit body does, and the page reflows it.'
  ''
  '- a bullet that wraps onto'
  '  a second line'
  '- another, which fixes #12; see https://example.com/issue'
  '* a star bullet with <b>bold</b> <script>alert(1)</script>'
  ''
  'An example:'
  ''
  '    indented code stays code'
  ''
  'A [link](https://example.com/doc) and a [relative one](docs/x.md).'
  ''
  'Signed-off-by: Test <test@example.com>'
  'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'
  > ../message.txt &&
  git commit -q -F ../message.txt &&
  printf 'chore: sign\n\nSigned-off-by: Test <test@example.com>\n' > ../signed.txt &&
  git commit -q --allow-empty -F ../signed.txt
---
# Golden Test: A Commit Body as Markdown

`/api/git/commit-markdown/<rev>` renders a commit message’s body through the path a pull
request’s description takes: KPress in its sanitized mode in the Markdown child, with
code plain, and the inert allowlist (`src/metabrowser/git/message.py`). The fixture’s
body is wrapped at 72 columns and has a list with each marker, an issue reference and a
bare URL, inline HTML with a script, indented code, an absolute and a relative link, and
Git’s trailers. The commit IDs are fixed by the pinned identity, dates, and messages.

## Test: the fixture’s commits

```console
$ git -C gitroot log --format='%H %s'
763a2e3f2e226b4fe326b3bdc40d6d3485ce7f12 chore: sign
672d1c8eb2fba8e3206539e22505446a83e4a02a feat: teach the app to count
? 0
```

## Test: a body renders as a description does

The wrapped prose is one paragraph, its newline a soft break.
Each list marker starts a list, and the wrapped item stays one item.
`#12` and the bare URL stay text, as they do in a description.
`<b>` is kept and the script is gone with its content; the indented code is code.
The absolute link opens in a new tab, and the relative one keeps only its text, since a
commit message has no page it could resolve against (`link_base`). The trailers are
split off as written, for the page to show as their own lines.

```console
$ metab gitroot --api /api/git/commit-markdown/672d1c8eb2fba8e3206539e22505446a83e4a02a
api: /api/git/commit-markdown/672d1c8eb2fba8e3206539e22505446a83e4a02a
status: 200
{
  "is_repo": true,
  "revision": "672d1c8eb2fba8e3206539e22505446a83e4a02a",
  "html": "\n<div><div><p>The app counted to one. This change wraps its prose at seventy-two\ncolumns, as a commit body does, and the page reflows it.</p>\n<ul>\n<li>a bullet that wraps onto\na second line</li>\n<li>another, which fixes #12; see https://example.com/issue</li>\n</ul>\n<ul>\n<li>a star bullet with <b>bold</b> </li>\n</ul>\n<p>An example:</p>\n<pre><code>indented code stays code\n</code></pre>\n<p>A <a href=\"https://example.com/doc\" target=\"_blank\" rel=\"noopener noreferrer\">link</a> and a <a>relative one</a>.</p></div></div>",
  "trailers": "Signed-off-by: Test <test@example.com>\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
  "link_base": "about:blank",
  "assets": {
...
  }
}
? 0
```

## Test: a body that is only trailers

Nothing is rendered; the trailers are the whole body.

```console
$ metab gitroot --api /api/git/commit-markdown/763a2e3f2e226b4fe326b3bdc40d6d3485ce7f12
api: /api/git/commit-markdown/763a2e3f2e226b4fe326b3bdc40d6d3485ce7f12
status: 200
{
  "is_repo": true,
  "revision": "763a2e3f2e226b4fe326b3bdc40d6d3485ce7f12",
  "html": "",
  "trailers": "Signed-off-by: Test <test@example.com>",
  "link_base": "about:blank",
  "assets": {
...
  }
}
? 0
```

## Test: a commit the repository lacks, and a short ID

```console
$ metab gitroot --api /api/git/commit-markdown/0000000000000000000000000000000000000000
api: /api/git/commit-markdown/0000000000000000000000000000000000000000
status: 404
{
  "error": "unknown revision",
  "code": "commit_not_found"
}
Error: /api/git/commit-markdown/0000000000000000000000000000000000000000 returned HTTP 404
? 1
```

```console
$ metab gitroot --api /api/git/commit-markdown/abc1234
api: /api/git/commit-markdown/abc1234
status: 400
{
  "error": "revision must be a full 40- or 64-character object id",
  "code": "revision_not_full"
}
Error: /api/git/commit-markdown/abc1234 returned HTTP 400
? 1
```
