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

`metab ROOT --present --dry-run --format json` resolves ROOT as every mode does and
prints what `--present` would hand the app: a `kind`, a `root` that is an absolute
folder or a canonical GitHub repository URL with no ref in it, the `page` that root
opens at or null where only the mirror knows it, the `handoff` that `open -b` is given,
and a `refusal` that is null.
A target it cannot present has null `kind`, `root`, `page`, and `handoff`, a refusal
with a stable code and a message that names the fix, and exit status 3. The macOS app
checks what a user types this way, so it parses no URL itself.

Nothing here looks for the app, clones, fetches, or starts a server.
Delivery to the app, with a recording `open`, is
`tests/golden/cli-present-delivery.txt`.

## Test: a folder, a file, and a selection inside a folder

```console
$ metab notes --present --dry-run --format json
{
  "kind": "folder",
  "root": "[CWD]/notes",
  "page": "/view/",
  "handoff": [
    "[CWD]/notes"
  ],
  "refusal": null
}
? 0
```

```console
$ metab notes --present --dry-run
kind: folder
root: [CWD]/notes
page: /view/
handoff: [CWD]/notes
? 0
```

A file is presented in the folder `metab FILE` serves, and a link where it points.
The handoff names the folder and then the file, so the app opens that folder.

```console
$ metab notes/README.md --present --dry-run --format json
{
  "kind": "file",
  "root": "[CWD]/notes",
  "page": "/view/README.md",
  "handoff": [
    "[CWD]/notes",
    "[CWD]/notes/README.md"
  ],
  "refusal": null
}
? 0
```

```console
$ metab notes/link.md --present --dry-run --format json
{
  "kind": "file",
  "root": "[CWD]/notes/docs",
  "page": "/view/guide.md",
  "handoff": [
    "[CWD]/notes/docs",
    "[CWD]/notes/docs/guide.md"
  ],
  "refusal": null
}
? 0
```

`--path` selects a file or a folder inside ROOT, as serve mode reads it.
A file is handed over after its root, so the app opens that root; a folder inside ROOT
has no handoff, because the app opens every folder in a window of its own.

```console
$ metab notes --path docs/guide.md --present --dry-run --format json
{
  "kind": "file",
  "root": "[CWD]/notes",
  "page": "/view/docs/guide.md",
  "handoff": [
    "[CWD]/notes",
    "[CWD]/notes/docs/guide.md"
  ],
  "refusal": null
}
? 0
```

```console
$ metab notes --path docs --present --dry-run --format json
{
  "kind": "folder",
  "root": "[CWD]/notes",
  "page": "/view/docs/",
  "handoff": null,
  "refusal": null
}
? 0
```

## Test: GitHub URLs, rooted at the repository

Every spelling of a repository is one root, and no root names a ref, because the app
keys a session by its repository.

```console
$ metab https://github.com/Octo/Demo.git --present --dry-run --format json
{
  "kind": "repository",
  "root": "https://github.com/octo/demo",
  "page": "/view/",
  "handoff": [
    "https://github.com/octo/demo"
  ],
  "refusal": null
}
? 0
```

```console
$ metab git@github.com:octo/demo.git --present --dry-run
kind: repository
root: https://github.com/octo/demo
page: /view/
handoff: https://github.com/octo/demo
? 0
```

A branch is a `tree` at the top of the repository, and a ref spelled in full or `HEAD`
leaves one reading of the path after it, so its page is known.

```console
$ metab https://github.com/octo/demo/tree/main --present --dry-run --format json
{
  "kind": "tree",
  "root": "https://github.com/octo/demo",
  "page": "/view/",
  "handoff": [
    "https://github.com/octo/demo/tree/main"
  ],
  "refusal": null
}
? 0
```

```console
$ metab https://github.com/octo/demo/tree/refs/tags/v1.0 --present --dry-run --format json
{
  "kind": "tree",
  "root": "https://github.com/octo/demo",
  "page": "/view/",
  "handoff": [
    "https://github.com/octo/demo/tree/refs/tags/v1.0"
  ],
  "refusal": null
}
? 0
```

```console
$ metab https://github.com/octo/demo/tree/HEAD/docs --present --dry-run --format json
{
  "kind": "tree",
  "root": "https://github.com/octo/demo",
  "page": "/view/g1-ZG9jcw/",
  "handoff": [
    "https://github.com/octo/demo/tree/HEAD/docs"
  ],
  "refusal": null
}
? 0
```

```console
$ metab https://raw.githubusercontent.com/octo/demo/refs/heads/main/README.md --present --dry-run --format json
{
  "kind": "file",
  "root": "https://github.com/octo/demo",
  "page": "/view/g1-UkVBRE1FLm1k",
  "handoff": [
    "https://github.com/octo/demo/blob/refs/heads/main/README.md"
  ],
  "refusal": null
}
? 0
```

A file keeps its `plain=1` and its line anchor.

```console
$ metab 'https://github.com/octo/demo/blob/HEAD/docs/guide.md?plain=1#L3-L5' --present --dry-run --format json
{
  "kind": "file",
  "root": "https://github.com/octo/demo",
  "page": "/view/g1-ZG9jcw/g1-Z3VpZGUubWQ?plain=1#L3-L5",
  "handoff": [
    "https://github.com/octo/demo/blob/HEAD/docs/guide.md?plain=1#L3-L5"
  ],
  "refusal": null
}
? 0
```

Where only the mirror knows where a ref ends, `page` is null, which the app reads as the
entry page of the server it starts; that server resolves the URL and opens the right
address. `claude/x` below may be a branch, or `claude` a branch with a folder `x`.

```console
$ metab https://github.com/octo/demo/tree/claude/x/docs --present --dry-run --format json
{
  "kind": "tree",
  "root": "https://github.com/octo/demo",
  "page": null,
  "handoff": [
    "https://github.com/octo/demo/tree/claude/x/docs"
  ],
  "refusal": null
}
? 0
```

```console
$ metab https://github.com/octo/demo/blob/main/docs/guide.md --present --dry-run
kind: file
root: https://github.com/octo/demo
page: (the server's entry page)
handoff: https://github.com/octo/demo/blob/main/docs/guide.md
? 0
```

A pull request opens on the tab its URL names, and a commit at its own page, which the
commit route answers for a full ID only, so an abbreviated one has a null `page`.

```console
$ metab https://github.com/octo/demo/pull/7 --present --dry-run --format json
{
  "kind": "pull_request",
  "root": "https://github.com/octo/demo",
  "page": "/pull/7",
  "handoff": [
    "https://github.com/octo/demo/pull/7"
  ],
  "refusal": null
}
? 0
```

```console
$ metab https://github.com/octo/demo/pull/7/checks --present --dry-run --format json
{
  "kind": "pull_request",
  "root": "https://github.com/octo/demo",
  "page": "/pull/7/checks",
  "handoff": [
    "https://github.com/octo/demo/pull/7/checks"
  ],
  "refusal": null
}
? 0
```

```console
$ metab https://github.com/octo/demo/commit/1A2B3C4D --present --dry-run --format json
{
  "kind": "commit",
  "root": "https://github.com/octo/demo",
  "page": null,
  "handoff": [
    "https://github.com/octo/demo/commit/1a2b3c4d"
  ],
  "refusal": null
}
? 0
```

```console
$ metab https://github.com/octo/demo/commit/0123456789ABCDEF0123456789abcdef01234567 --present --dry-run --format json
{
  "kind": "commit",
  "root": "https://github.com/octo/demo",
  "page": "/commit/0123456789abcdef0123456789abcdef01234567",
  "handoff": [
    "https://github.com/octo/demo/commit/0123456789abcdef0123456789abcdef01234567"
  ],
  "refusal": null
}
? 0
```

```console
$ metab https://github.com/octo/demo/pull/7/commits/0123456789abcdef0123456789abcdef01234567 --present --dry-run --format json
{
  "kind": "commit",
  "root": "https://github.com/octo/demo",
  "page": "/commit/0123456789abcdef0123456789abcdef01234567",
  "handoff": [
    "https://github.com/octo/demo/pull/7/commits/0123456789abcdef0123456789abcdef01234567"
  ],
  "refusal": null
}
? 0
```

## Test: local targets that cannot be presented

```console
$ metab missing --present --dry-run --format json
{
  "kind": null,
  "root": null,
  "page": null,
  "handoff": null,
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
$ metab notes/pipe --present --dry-run --format json
{
  "kind": null,
  "root": null,
  "page": null,
  "handoff": null,
  "refusal": {
    "code": "not_a_file_or_folder",
    "message": "[CWD]/notes/pipe is neither a file nor a folder; present a file or a folder"
  }
}
? 3
```

```console
$ metab notes/README.md --path docs --present --dry-run --format json
{
  "kind": null,
  "root": null,
  "page": null,
  "handoff": null,
  "refusal": {
    "code": "path_with_file",
    "message": "--path selects inside a folder, and ROOT is a file; present the file alone, or name its folder as ROOT"
  }
}
? 3
```

```console
$ metab notes --path nope.md --present --dry-run --format json
{
  "kind": null,
  "root": null,
  "page": null,
  "handoff": null,
  "refusal": {
    "code": "path_not_found",
    "message": "--path names nothing in [CWD]/notes; check nope.md"
  }
}
? 3
```

```console
$ metab notes/docs --path ../README.md --present --dry-run --format json
{
  "kind": null,
  "root": null,
  "page": null,
  "handoff": null,
  "refusal": {
    "code": "path_outside_root",
    "message": "--path names a place outside [CWD]/notes/docs; name one inside it"
  }
}
? 3
```

```console
$ metab '' --present --dry-run --format json
{
  "kind": null,
  "root": null,
  "page": null,
  "handoff": null,
  "refusal": {
    "code": "empty",
    "message": "ROOT is empty; write . for the current folder"
  }
}
? 3
```

## Test: URLs that cannot be presented

A GitHub page that is not a repository view is refused with the reducer’s own reason and
message, which never repeats the URL.

```console
$ metab https://github.com/octo/demo/issues/5 --present --dry-run --format json
{
  "kind": null,
  "root": null,
  "page": null,
  "handoff": null,
  "refusal": {
    "code": "unsupported_github_url",
    "message": "GitHub issues pages are not opened; open the repository at https://github.com/octo/demo"
  }
}
? 3
```

```console
$ metab https://github.com/octo/demo/pull/0 --present --dry-run --format json
{
  "kind": null,
  "root": null,
  "page": null,
  "handoff": null,
  "refusal": {
    "code": "invalid_pull_request",
    "message": "a pull request URL names a positive number; open the repository at https://github.com/octo/demo"
  }
}
? 3
```

```console
$ metab http://github.com/octo/demo --present --dry-run --format json
{
  "kind": null,
  "root": null,
  "page": null,
  "handoff": null,
  "refusal": {
    "code": "insecure_http",
    "message": "GitHub is opened over https; use https://github.com/octo/demo"
  }
}
? 3
```

```console
$ metab https://ghp_example@github.com/octo/demo --present --dry-run --format json
{
  "kind": null,
  "root": null,
  "page": null,
  "handoff": null,
  "refusal": {
    "code": "credentials_in_url",
    "message": "the URL carries credentials"
  }
}
? 3
```

A Git source that is not on GitHub is served with `metab URL`, not presented.

```console
$ metab https://example.com/octo/demo.git --present --dry-run --format json
{
  "kind": null,
  "root": null,
  "page": null,
  "handoff": null,
  "refusal": {
    "code": "unsupported_source",
    "message": "--present opens a local file or folder, or a GitHub URL; give one of those"
  }
}
? 3
```

```console
$ metab file:///srv/git/demo.git --present --dry-run --format json
{
  "kind": null,
  "root": null,
  "page": null,
  "handoff": null,
  "refusal": {
    "code": "unsupported_source",
    "message": "--present opens a local file or folder, or a GitHub URL; give one of those"
  }
}
? 3
```

```console
$ metab ftp://example.com/demo --present --dry-run --format json
{
  "kind": null,
  "root": null,
  "page": null,
  "handoff": null,
  "refusal": {
    "code": "unsupported_transport",
    "message": "ROOT is neither a path that exists nor a GitHub URL; give a local file or folder, or a github.com URL"
  }
}
? 3
```

`--path` selects inside a local folder only: the app is handed one URL.

```console
$ metab https://github.com/octo/demo --path README.md --present --dry-run --format json
{
  "kind": null,
  "root": null,
  "page": null,
  "handoff": null,
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
$ metab notes --present --dry-run --json 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ --json not valid with --present                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

```console
$ metab notes --present --dry-run --format yaml 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ --format yaml is not valid with --present; choose json or text               │
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
