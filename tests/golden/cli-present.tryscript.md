---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
patterns:
  ROOT_ARG: '\[ROOT\]'
before: >-
  mkdir -p notes/docs &&
  printf '# Notes\n' > notes/README.md &&
  printf '# Guide\n' > notes/docs/guide.md &&
  ln -s docs/guide.md notes/link.md &&
  mkfifo notes/pipe
---
# Golden tests: what `--present` hands the macOS app

`metab TARGET --present --dry-run --json` resolves TARGET as ROOT is resolved and prints
what `--present` would hand the app: a `kind`, a `root` that is an absolute folder or a
canonical GitHub repository URL with no ref in it, the `page` that root opens at, and a
`refusal` that is null.
A target it cannot present has null `kind`, `root`, and `page`, a refusal with a stable
code and a message that names the fix, and exit status 3. The macOS app checks what a
user types this way, so it parses no URL itself.

Nothing here looks for the app, clones, fetches, or starts a server.
Delivery to the app, with a recording `open`, is
`tests/golden/cli-present-delivery.txt`.

## Test: a folder, a file, and a selection inside a folder

```console
$ metab notes --present --dry-run --json
{
  "kind": "folder",
  "root": "[CWD]/notes",
  "page": "/view/",
  "refusal": null
}
? 0
```

```console
$ metab notes --present --dry-run
kind: folder
root: [CWD]/notes
page: /view/
? 0
```

A file is presented in the folder `metab FILE` serves, and a link where it points.

```console
$ metab notes/README.md --present --dry-run --json
{
  "kind": "file",
  "root": "[CWD]/notes",
  "page": "/view/README.md",
  "refusal": null
}
? 0
```

```console
$ metab notes/link.md --present --dry-run --json
{
  "kind": "file",
  "root": "[CWD]/notes/docs",
  "page": "/view/guide.md",
  "refusal": null
}
? 0
```

`--path` keeps its meaning: a file or a folder inside ROOT.

```console
$ metab notes --path docs/guide.md --present --dry-run --json
{
  "kind": "file",
  "root": "[CWD]/notes",
  "page": "/view/docs/guide.md",
  "refusal": null
}
? 0
```

```console
$ metab notes --path docs --present --dry-run --json
{
  "kind": "folder",
  "root": "[CWD]/notes",
  "page": "/view/docs/",
  "refusal": null
}
? 0
```

## Test: GitHub URLs, rooted at the repository

Every spelling of a repository is one root, and no root names a ref, because the app
keys a session by its repository.

```console
$ metab https://github.com/Octo/Demo.git --present --dry-run --json
{
  "kind": "repository",
  "root": "https://github.com/octo/demo",
  "page": "/view/",
  "refusal": null
}
? 0
```

```console
$ metab git@github.com:octo/demo.git --present --dry-run
kind: repository
root: https://github.com/octo/demo
page: /view/
? 0
```

A branch is a `tree` at the top of the repository.
Under it, a path opens at the address a pinned server spells it with; the first segment
is read as the ref, and the server the app starts resolves a ref containing `/` itself.

```console
$ metab https://github.com/octo/demo/tree/main --present --dry-run --json
{
  "kind": "tree",
  "root": "https://github.com/octo/demo",
  "page": "/view/",
  "refusal": null
}
? 0
```

```console
$ metab https://github.com/octo/demo/tree/main/docs --present --dry-run --json
{
  "kind": "tree",
  "root": "https://github.com/octo/demo",
  "page": "/view/g1-ZG9jcw/",
  "refusal": null
}
? 0
```

A file keeps its `plain=1` and its line anchor.

```console
$ metab 'https://github.com/octo/demo/blob/main/docs/guide.md?plain=1#L3-L5' --present --dry-run --json
{
  "kind": "file",
  "root": "https://github.com/octo/demo",
  "page": "/view/g1-ZG9jcw/g1-Z3VpZGUubWQ?plain=1#L3-L5",
  "refusal": null
}
? 0
```

A pull request opens on the tab its URL names, and a commit at its own page.

```console
$ metab https://github.com/octo/demo/pull/7 --present --dry-run --json
{
  "kind": "pull_request",
  "root": "https://github.com/octo/demo",
  "page": "/pull/7",
  "refusal": null
}
? 0
```

```console
$ metab https://github.com/octo/demo/pull/7/checks --present --dry-run --json
{
  "kind": "pull_request",
  "root": "https://github.com/octo/demo",
  "page": "/pull/7/checks",
  "refusal": null
}
? 0
```

```console
$ metab https://github.com/octo/demo/commit/1A2B3C4D --present --dry-run --json
{
  "kind": "commit",
  "root": "https://github.com/octo/demo",
  "page": "/commit/1a2b3c4d",
  "refusal": null
}
? 0
```

```console
$ metab https://github.com/octo/demo/pull/7/commits/0123456789abcdef0123456789abcdef01234567 --present --dry-run --json
{
  "kind": "commit",
  "root": "https://github.com/octo/demo",
  "page": "/commit/0123456789abcdef0123456789abcdef01234567",
  "refusal": null
}
? 0
```

## Test: local targets that cannot be presented

```console
$ metab missing --present --dry-run --json
{
  "kind": null,
  "root": null,
  "page": null,
  "refusal": {
    "code": "not_found",
    "message": "nothing is at [CWD]/missing; check the path"
  }
}
? 3
```

```console
$ metab missing --present --dry-run 2>&1
Error: nothing is at [CWD]/missing; check the path (not_found)
? 3
```

```console
$ metab notes/pipe --present --dry-run --json
{
  "kind": null,
  "root": null,
  "page": null,
  "refusal": {
    "code": "not_a_file_or_folder",
    "message": "[CWD]/notes/pipe is neither a file nor a folder; present a file or a folder"
  }
}
? 3
```

```console
$ metab notes/README.md --path docs --present --dry-run --json
{
  "kind": null,
  "root": null,
  "page": null,
  "refusal": {
    "code": "path_with_file",
    "message": "--path selects inside a folder, and TARGET is a file; present the file alone, or name its folder as TARGET"
  }
}
? 3
```

```console
$ metab notes --path nope.md --present --dry-run --json
{
  "kind": null,
  "root": null,
  "page": null,
  "refusal": {
    "code": "path_not_found",
    "message": "--path names nothing in [CWD]/notes; check nope.md"
  }
}
? 3
```

```console
$ metab notes/docs --path ../README.md --present --dry-run --json
{
  "kind": null,
  "root": null,
  "page": null,
  "refusal": {
    "code": "path_outside_root",
    "message": "--path names a place outside [CWD]/notes/docs; name one inside it"
  }
}
? 3
```

```console
$ metab '' --present --dry-run --json
{
  "kind": null,
  "root": null,
  "page": null,
  "refusal": {
    "code": "empty",
    "message": "TARGET is empty; write . for the current folder"
  }
}
? 3
```

## Test: URLs that cannot be presented

A GitHub page that is not a repository view is refused with the reducer’s own reason and
message, which never repeats the URL.

```console
$ metab https://github.com/octo/demo/issues/5 --present --dry-run --json
{
  "kind": null,
  "root": null,
  "page": null,
  "refusal": {
    "code": "unsupported_github_url",
    "message": "GitHub issues pages are not opened; open the repository at https://github.com/octo/demo"
  }
}
? 3
```

```console
$ metab https://github.com/octo/demo/pull/0 --present --dry-run --json
{
  "kind": null,
  "root": null,
  "page": null,
  "refusal": {
    "code": "invalid_pull_request",
    "message": "a pull request URL names a positive number; open the repository at https://github.com/octo/demo"
  }
}
? 3
```

```console
$ metab http://github.com/octo/demo --present --dry-run --json
{
  "kind": null,
  "root": null,
  "page": null,
  "refusal": {
    "code": "insecure_http",
    "message": "GitHub is opened over https; use https://github.com/octo/demo"
  }
}
? 3
```

```console
$ metab https://ghp_example@github.com/octo/demo --present --dry-run --json
{
  "kind": null,
  "root": null,
  "page": null,
  "refusal": {
    "code": "credentials_in_url",
    "message": "the URL carries credentials"
  }
}
? 3
```

A Git source that is not on GitHub is served with `metab URL`, not presented.

```console
$ metab https://example.com/octo/demo.git --present --dry-run --json
{
  "kind": null,
  "root": null,
  "page": null,
  "refusal": {
    "code": "unsupported_source",
    "message": "--present opens a local file or folder, or a GitHub URL; serve another Git source with metab URL"
  }
}
? 3
```

```console
$ metab file:///srv/git/demo.git --present --dry-run --json
{
  "kind": null,
  "root": null,
  "page": null,
  "refusal": {
    "code": "unsupported_source",
    "message": "--present opens a local file or folder, or a GitHub URL; serve another Git source with metab URL"
  }
}
? 3
```

```console
$ metab ftp://example.com/demo --present --dry-run --json
{
  "kind": null,
  "root": null,
  "page": null,
  "refusal": {
    "code": "unsupported_transport",
    "message": "TARGET is neither a path that exists nor a GitHub URL; give a local file or folder, or a github.com URL"
  }
}
? 3
```

`--path` selects inside a local folder only: the app is handed one URL.

```console
$ metab https://github.com/octo/demo --path README.md --present --dry-run --json
{
  "kind": null,
  "root": null,
  "page": null,
  "refusal": {
    "code": "path_with_url",
    "message": "--path selects inside a local folder; for a GitHub URL, present the URL of the file or folder itself"
  }
}
? 3
```

## Test: usage errors stay status 2

```console
$ metab notes --present --dry-run --app-bundle-id org.example.viewer 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ --app-bundle-id not valid with --present --dry-run, which looks for no app   │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

```console
$ metab --present --dry-run 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ ROOT is required for --present; e.g. `metab . --present`                     │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

```console
$ metab notes --present --walk 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ mode flags are mutually exclusive; got --walk and --present                  │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

```console
$ metab notes --walk --dry-run 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ --dry-run not valid with --walk                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

```console
$ metab notes --present --dry-run --port 9000 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ --port not valid with --present                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
