---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
  METABROWSER_OPEN_IN: "browser"
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

A target that resolves also carries a `decision`: where `--present` would open it, the
app or a browser, and why.
This file sets `METABROWSER_OPEN_IN=browser`, so the decision is the same on every
machine: nothing here looks for the app, clones, fetches, or starts a server.
Decisions under each preference, and delivery to the app with a recording `open`, are
`tests/golden/cli-present-delivery.txt`; delivery to a browser on a stand-in server is
`tests/golden/cli-present-browser.txt`.

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
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
}
? 0
```

```console
$ metab notes --present --dry-run
kind: folder
root: [CWD]/notes
page: /view/
handoff: [CWD]/notes
open_in: browser (environment)
delivers_to: browser
code: browser_preferred
reason: open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser
? 0
```

A file is presented in the folder `metab FILE` serves, and a link where it points.
The handoff is the file alone, which the app places in the most specific folder it has
open that holds it, and otherwise opens in that folder.

```console
$ metab notes/README.md --present --dry-run --format json
{
  "kind": "file",
  "root": "[CWD]/notes",
  "page": "/view/README.md",
  "handoff": [
    "[CWD]/notes/README.md"
  ],
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
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
    "[CWD]/notes/docs/guide.md"
  ],
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
}
? 0
```

`--path` selects a file or a folder inside ROOT, as serve mode reads it.
A file is handed over after the ROOT named, so the app opens that root; a folder inside
ROOT has no handoff, because the app opens every folder in a window of its own.

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
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
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
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
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
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
}
? 0
```

```console
$ metab git@github.com:octo/demo.git --present --dry-run
kind: repository
root: https://github.com/octo/demo
page: /view/
handoff: https://github.com/octo/demo
open_in: browser (environment)
delivers_to: browser
code: browser_preferred
reason: open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser
? 0
```

A GitHub URL typed without `https://`, which names nothing on disk, is the full URL.

```console
$ metab github.com/octo/demo/pull/7 --present --dry-run
kind: pull_request
root: https://github.com/octo/demo
page: /pull/7
handoff: https://github.com/octo/demo/pull/7
open_in: browser (environment)
delivers_to: browser
code: browser_preferred
reason: open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser
? 0
```

A branch is a `tree` at the top of the repository, named alone or spelled in full, and a
path after `HEAD` has one reading, so their pages are known.

```console
$ metab https://github.com/octo/demo/tree/main --present --dry-run --format json
{
  "kind": "tree",
  "root": "https://github.com/octo/demo",
  "page": "/view/",
  "handoff": [
    "https://github.com/octo/demo/tree/main"
  ],
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
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
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
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
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
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
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
}
? 0
```

Where only the mirror knows where a ref ends, `page` is null, which the app reads as the
entry page of the server it starts; that server resolves the URL and opens the right
address. `claude/x` below may be a branch, or `claude` a branch with a folder `x`. A
`blob` URL’s last two segments may be a branch and a file, or one branch such as
`release/v1`, which `metab URL` serves at `/view/`, so no `blob` but one after `HEAD`
has a page here.

```console
$ metab https://github.com/octo/demo/tree/claude/x/docs --present --dry-run --format json
{
  "kind": "tree",
  "root": "https://github.com/octo/demo",
  "page": null,
  "handoff": [
    "https://github.com/octo/demo/tree/claude/x/docs"
  ],
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
}
? 0
```

```console
$ metab https://raw.githubusercontent.com/octo/demo/refs/heads/main/README.md --present --dry-run --format json
{
  "kind": "file",
  "root": "https://github.com/octo/demo",
  "page": null,
  "handoff": [
    "https://github.com/octo/demo/blob/refs/heads/main/README.md"
  ],
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
}
? 0
```

```console
$ metab https://github.com/octo/demo/blob/release/v1 --present --dry-run --format json
{
  "kind": "file",
  "root": "https://github.com/octo/demo",
  "page": null,
  "handoff": [
    "https://github.com/octo/demo/blob/release/v1"
  ],
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
}
? 0
```

```console
$ metab https://github.com/octo/demo/blob/main/docs/guide.md --present --dry-run
kind: file
root: https://github.com/octo/demo
page: (the server's entry page)
handoff: https://github.com/octo/demo/blob/main/docs/guide.md
open_in: browser (environment)
delivers_to: browser
code: browser_preferred
reason: open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser
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
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
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
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
}
? 0
```

GitHub anchors one file of a pull request’s Changes tab as `diff-` and the SHA-256 of
its path, optionally followed by a line of that file’s diff.
Only the pull request’s list of changed files, in the cache, says which file the hash
names, so the `page` is null, and the `handoff` keeps the anchor for the server the app
starts, which opens at the file it names or at the Changes tab where nothing it has
cached names one (`cli-github-pull-file-anchor.txt`). Any other fragment there is
dropped, as it is on a blob.

```console
$ metab 'https://github.com/octo/demo/pull/7/files#diff-be97662273fac8ac301e8dfa98ba5d8d90d390bfa9419746155382b7ace0a3c2R2' --present --dry-run --format json
{
  "kind": "pull_request",
  "root": "https://github.com/octo/demo",
  "page": null,
  "handoff": [
    "https://github.com/octo/demo/pull/7/files#diff-be97662273fac8ac301e8dfa98ba5d8d90d390bfa9419746155382b7ace0a3c2R2"
  ],
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
}
? 0
```

```console
$ metab 'https://github.com/octo/demo/pull/7/files#diff-be97662273fac8ac' --present --dry-run --format json
{
  "kind": "pull_request",
  "root": "https://github.com/octo/demo",
  "page": "/pull/7/files",
  "handoff": [
    "https://github.com/octo/demo/pull/7/files"
  ],
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
}
? 0
```

GitHub’s Changes page is `/pull/<n>/changes` since 2026-01-22, and `/files` its older
spelling, which GitHub redirects there.
Both select the Changes tab, with or without a file anchor, and the `handoff` spells the
URL `/files`, which GitHub answers either way.

```console
$ metab 'https://github.com/octo/demo/pull/7/changes#diff-be97662273fac8ac301e8dfa98ba5d8d90d390bfa9419746155382b7ace0a3c2R2' --present --dry-run --format json
{
  "kind": "pull_request",
  "root": "https://github.com/octo/demo",
  "page": null,
  "handoff": [
    "https://github.com/octo/demo/pull/7/files#diff-be97662273fac8ac301e8dfa98ba5d8d90d390bfa9419746155382b7ace0a3c2R2"
  ],
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
}
? 0
```

```console
$ metab https://github.com/octo/demo/pull/7/changes --present --dry-run --format json
{
  "kind": "pull_request",
  "root": "https://github.com/octo/demo",
  "page": "/pull/7/files",
  "handoff": [
    "https://github.com/octo/demo/pull/7/files"
  ],
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
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
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
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
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
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
  "refusal": null,
  "decision": {
    "delivers_to": "browser",
    "open_in": "browser",
    "open_in_source": "environment",
    "bundle_id": null,
    "bundle_path": null,
    "code": "browser_preferred",
    "reason": "open_in is browser, so --present looks for no app and starts a metab server for the target that opens it in a browser",
    "fallback": null
  }
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
  },
  "decision": null
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
  },
  "decision": null
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
  },
  "decision": null
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
  },
  "decision": null
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
  },
  "decision": null
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
  },
  "decision": null
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
  },
  "decision": null
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
  },
  "decision": null
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
  },
  "decision": null
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
  },
  "decision": null
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
  },
  "decision": null
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
  },
  "decision": null
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
  },
  "decision": null
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
  },
  "decision": null
}
? 3
```

## Test: usage errors stay status 2

```console
$ metab notes --present --dry-run --open-in browser --app-bundle-id org.example.viewer 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ --app-bundle-id not valid with --open-in browser, which looks for no app     │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

A sandbox rule for `metab --present` matches whatever follows it, so no option may
choose the `config.yml` whose `present_browser` the command obeys.

```console
$ metab notes --present --dry-run --open-in browser --config-dir notes 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ --config-dir not valid with --present, so no option lifts present_browser    │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

```console
$ metab notes --present --dry-run --open-in sometimes 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ Invalid value for --open-in: 'sometimes' is not one of auto, app, browser    │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

```console
$ metab notes --walk --open-in app 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ --open-in not valid with --walk                                              │
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
