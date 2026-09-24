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
  GIT_CONFIG_NOSYSTEM: "1"
---
# Golden tests: GitHub URLs a user pastes

The built-in GitHub reducer claims `github.com` and `raw.githubusercontent.com` URLs
before the generic grammar runs.
It turns every spelling of one repository into the canonical
`https://github.com/<owner>/<repo>` source and refuses every other shape with a reason
and a message that names the shape and offers the repository URL.
`tests/test_github_url_reducer.py` covers every shape; this transcript shows what
reaches the terminal.

No command here reaches Git or the network.
A refused URL stops at classification, and an accepted one is shown through `--walk`,
which refuses a Git source before acquiring it.
Opening each accepted shape end to end, with the selection it resolves to, is in
`tests/test_cli_github_url_golden.py`, which stands a local origin in for GitHub.

A refusal never repeats the argument, so a token in a refused URL does not reach the
terminal. The last test shows that no command created the application home.

## Test: every spelling of a repository is one canonical source

Owner and repository fold to lowercase; `.git`, a trailing slash, `www.`, the default
port, tracking parameters, and a fragment are dropped; an SSH address is rewritten to
HTTPS.

```console
$ METABROWSER_HOME=$PWD/home metab https://www.github.com/Octo/Demo.git/ --walk
Error: --walk runs the filesystem inventory walker, and a Git source has no filesystem to walk (https://github.com/octo/demo). Read a pinned tree with --api '/api/tree?depth=N', or --walk a local directory.
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab 'https://github.com:443/octo/demo?tab=readme-ov-file#readme' --walk
Error: --walk runs the filesystem inventory walker, and a Git source has no filesystem to walk (https://github.com/octo/demo). Read a pinned tree with --api '/api/tree?depth=N', or --walk a local directory.
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab git@github.com:octo/demo.git --walk
Error: --walk runs the filesystem inventory walker, and a Git source has no filesystem to walk (https://github.com/octo/demo). Read a pinned tree with --api '/api/tree?depth=N', or --walk a local directory.
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab 'https://github.com/octo/demo/blob/release/v1/docs/a.md?plain=1#L10C5-L20C8' --walk
Error: --walk runs the filesystem inventory walker, and a Git source has no filesystem to walk (https://github.com/octo/demo). Read a pinned tree with --api '/api/tree?depth=N', or --walk a local directory.
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://raw.githubusercontent.com/octo/demo/refs/heads/topic/a.md --walk
Error: --walk runs the filesystem inventory walker, and a Git source has no filesystem to walk (https://github.com/octo/demo). Read a pinned tree with --api '/api/tree?depth=N', or --walk a local directory.
? 1
```

## Test: pages that are not repository views are refused by shape

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/demo/issues/5 --no-serve
Error: invalid ROOT (unsupported_github_url): GitHub issues pages are not opened; open the repository at https://github.com/octo/demo
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/demo/some-token-like-text --no-serve
Error: invalid ROOT (unsupported_github_url): this GitHub page is not opened; open the repository at https://github.com/octo/demo
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/demo/blob/topic --show README.md
Error: invalid ROOT (unsupported_github_url): a blob URL names a ref and a file; open https://github.com/octo/demo
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/demo/pull/12/checks --api /api/git/repo
Error: invalid ROOT (unsupported_github_url): this GitHub page is not opened; open the repository at https://github.com/octo/demo
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo --no-serve
Error: invalid ROOT (unsupported_github_url): github.com/octo is an account page, not a repository
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/ --no-serve
Error: invalid ROOT (unsupported_github_url): github.com itself is not a repository; open https://github.com/<owner>/<repository>
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/settings/profile --no-serve
Error: invalid ROOT (reserved_owner): github.com/settings is a GitHub page, not a repository
? 1
```

## Test: http, other ports, and SSH users

```console
$ METABROWSER_HOME=$PWD/home metab http://github.com/octo/demo --no-serve
Error: invalid ROOT (insecure_http): GitHub is opened over https; use https://github.com/octo/demo
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com:8443/octo/demo --no-serve
Error: invalid ROOT (unsupported_port): GitHub answers on its standard port; use https://github.com/octo/demo
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab deploy@github.com:octo/demo.git --no-serve
Error: invalid ROOT (invalid_user): GitHub's SSH address uses the user git
? 1
```

## Test: owners, repositories, pull requests, and commits that are not valid

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/o_o/demo --no-serve
Error: invalid ROOT (invalid_owner): the owner is not a GitHub account name
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab 'https://github.com/octo/de$mo' --no-serve
Error: invalid ROOT (invalid_repository): the repository name is not a GitHub repository name
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/demo/pull/0 --no-serve
Error: invalid ROOT (invalid_pull_request): a pull request URL names a positive number; open the repository at https://github.com/octo/demo
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/demo/commit/not-hex --no-serve
Error: invalid ROOT (invalid_commit_id): a commit URL names a commit ID of 7 to 64 hexadecimal digits; open the repository at https://github.com/octo/demo
? 1
```

## Test: the generic checks still apply to a claimed URL

```console
$ METABROWSER_HOME=$PWD/home metab https://ghp_example@github.com/octo/demo --no-serve
Error: invalid ROOT (credentials_in_url): the URL carries credentials
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab 'https://github.com/octo/demo/blob/topic/my file.md' --no-serve
Error: invalid ROOT (control_or_whitespace): the URL contains a control character or space
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/démo --no-serve
Error: invalid ROOT (non_ascii): the URL contains a character outside ASCII
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/demo/tree/topic/%2e%2e/x --no-serve
Error: invalid ROOT (dot_segment): the URL path has a '.' or '..' segment
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://github.com/octo/demo/tree/topic%2Fx --no-serve
Error: invalid ROOT (encoded_delimiter): the URL path encodes a path separator
? 1
```

## Test: no command created the application home

```console
$ test -e home || echo "no application home"
no application home
```
