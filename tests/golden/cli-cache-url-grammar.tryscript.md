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
before: >-
  mkdir -p file:notes a::b me@host:dir https:x ./-dash
  https:/example.com/served/repo.git git@github.com:octo/demo ext::folder &&
  printf 'local\n' > git@github.com:octo/demo/local.txt &&
  printf 'ext\n' > ext::folder/ext.txt &&
  printf '# Notes\n' > file:notes/README.md &&
  printf 'b\n' > a::b/b.txt &&
  printf 'dir\n' > me@host:dir/dir.txt &&
  printf 'x\n' > https:x/x.txt &&
  printf 'dash\n' > ./-dash/dash.txt &&
  printf 'served\n' > https:/example.com/served/repo.git/served.txt &&
  touch -t 202311142213.20 file:notes/README.md file:notes
---
# Golden tests: the ROOT grammar a user sees

`metab` serves a ROOT that names an existing path, and classifies every other ROOT
before it builds a path or runs Git.
The frozen grammar is `tests/fixtures/repository-cache/url-grammar.json`, and
`tests/test_repository_cache_contract_fixtures.py` replays every case against the
production classifier.
That replay is the authority for the grammar: every normalization and every refusal
reason has its cases there.
This transcript shows what the fixture cannot, which is what reaches the terminal: one
input per accepted form, the refusal line, and the rule that an existing path is served.

No command reaches Git or the network, so this runs as a subprocess on any Git version.
A refused input stops at classification.
An accepted https or `file://` source is normalized and shown through `--walk`, which
refuses a Git source before acquiring it; an accepted ssh source is normalized and then
refused by acquisition before Git runs.
Serving or acquiring one needs a Git at or above the floor, so those sessions are in
`tests/test_cli_cache_acquire_golden.py` and `tests/test_cli_cache_recovery_golden.py`.
GitHub URLs are claimed by the GitHub reducer first; their transcript is
`cli-github-urls.tryscript.md`.

A refusal names its reason and never repeats the argument, so a credential or query in a
rejected URL does not reach the terminal.
Every command names an application home in the sandbox, and the last test shows that
none of them created it.

## Test: https sources are normalized

The scheme and host fold to lowercase, and the default port and a trailing slash are
dropped. The path keeps its case.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab HTTPS://Example.COM:443/Owner/Repo.git/ --walk
Error: --walk runs the filesystem inventory walker, and a Git source has no filesystem to walk (https://example.com/Owner/Repo.git). Read a pinned tree with --api '/api/tree?depth=N', or --walk a local directory.
? 1
```

## Test: ssh URLs and scp-like addresses are ssh sources

The default port 22 is dropped and the host folds to lowercase.
An scp-like address keeps its path as written, and is refused in the route mode as in
the acquisition mode.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab ssh://git@Example.com:22/owner/repo.git --no-serve
Error: ssh Git sources are not acquired yet (ssh://git@example.com/owner/repo.git)
? 1
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab git@example.com:owner/repo.git --api /api/cache/layout
Error: ssh Git sources are not acquired yet (git@example.com:owner/repo.git)
? 1
```

## Test: file sources name this machine

`localhost` folds to the empty authority, and a trailing slash is dropped.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab FILE://LocalHost/srv/git/repo.git/ --walk
Error: --walk runs the filesystem inventory walker, and a Git source has no filesystem to walk (file:///srv/git/repo.git). Read a pinned tree with --api '/api/tree?depth=N', or --walk a local directory.
? 1
```

## Test: a bare path is never a clone origin

A path stays a local path, and `--no-serve` has nothing to acquire.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab /srv/git/repo.git --no-serve
Error: ROOT is a local path; --no-serve acquires a file:// or https:// Git source
? 1
```

A path the grammar has to decide is the path that was given.
`a/b::c` holds `::`, so the grammar is asked; it names nothing here, and the error is
about that path and not about the working directory.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab a/b::c --walk
Error: [CWD]/a/b::c is not a directory
? 1
```

## Test: an existing path is served, whatever its name resembles

A folder may be called `file:notes`, `a::b`, `me@host:dir`, or `https:x`, names the
grammar would refuse or read as an ssh address.
An argument that names an existing path is that path, so each is served as a local
folder, as it was before ROOT was classified.
The `before` command creates them in the sandbox.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab file:notes --api '/api/tree?depth=1'
api: /api/tree?depth=1
status: 200
{
  "root": "<ROOT>",
  "tree": [
    {
      "name": "README.md",
      "path": "README.md",
      "type": "file",
      "size": 8,
      "mtime": 1700000000.0,
      "ext": ".md"
    }
  ],
  "filtered": null,
  "tally_cache_status": "done",
  "tally_cache_max_files": 500000,
  "summary": null,
  "file_type_registry": null,
  "extensions": null,
  "canonical_extensions": null,
  "type_families": null,
  "type_presets": null,
  "recency_tallies": null
}
? 0
```

`/api/source/status` names the subject: the filesystem, not a pin.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab me@host:dir --api /api/source/status
api: /api/source/status
status: 200
{
  "subject": "attached_filesystem",
  "generation": 1,
  "pin": null,
  "ref": null,
  "ref_name": null,
  "name": null,
  "origin": null,
  "location": null,
  "refreshable": false,
  "latest": null,
  "ref_on_origin": null,
  "last_fetch_at": null,
  "last_outcome": null,
  "refreshing": false,
  "stale": false,
  "pull_request": null,
  "selection_state": null,
  "selection_href": null
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab a::b --walk
walk: a::b
status: done
counts: files=1 dirs=1 symlinks=0
totals: total_files=1 total_size=2

entries:
  . [dir] files=1 size=2
  b.txt [file] size=2
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https:x --walk
walk: https:x
status: done
counts: files=1 dirs=1 symlinks=0
totals: total_files=1 total_size=2

entries:
  . [dir] files=1 size=2
  x.txt [file] size=2
? 0
```

A name that starts with a dash is reached past `--`, and is a path like the others.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab --walk -- -dash
walk: -dash
status: done
counts: files=1 dirs=1 symlinks=0
totals: total_files=1 total_size=5

entries:
  . [dir] files=1 size=5
  dash.txt [file] size=5
? 0
```

An scp-like address is a path too when the path exists.
`git@github.com:octo/demo` names the folder `demo` inside `git@github.com:octo` here, so
that folder is walked and GitHub is never asked; only `scheme://`, below, is exempt from
this.
With no such folder the same shape is the GitHub repository, which `--walk` refuses
before acquiring.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab git@github.com:octo/demo --walk
walk: demo
status: done
counts: files=1 dirs=1 symlinks=0
totals: total_files=1 total_size=6

entries:
  . [dir] files=1 size=6
  local.txt [file] size=6
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab git@github.com:octo/absent --walk
Error: --walk runs the filesystem inventory walker, and a Git source has no filesystem to walk (https://github.com/octo/absent). Read a pinned tree with --api '/api/tree?depth=N', or --walk a local directory.
? 1
```

Remote-helper syntax that names a folder is that folder; with none it is refused, as in
a later test.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab ext::folder --walk
walk: ext::folder
status: done
counts: files=1 dirs=1 symlinks=0
totals: total_files=1 total_size=4

entries:
  . [dir] files=1 size=4
  ext.txt [file] size=4
? 0
```

`--no-serve` has nothing to acquire from a local path.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab me@host:dir --no-serve
Error: ROOT is a local path; --no-serve acquires a file:// or https:// Git source
? 1
```

The same shapes name nothing here, so the grammar decides, as in the tests below.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab file:absent --walk
Error: invalid ROOT (malformed_url)
? 1
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab me@host:absent --no-serve
Error: ssh Git sources are not acquired yet (me@host:absent)
? 1
```

## Test: a `scheme://` argument is a source, whatever exists on disk

A path never needs that spelling: the system reads `https://example.com/served/repo.git`
as the path `https:/example.com/served/repo.git`, which exists in this sandbox.
The URL is still a Git source, so what a pasted URL opens does not depend on the working
directory, and a folder cannot stand in for the repository a URL names.
The one-slash spelling reaches the folder.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://example.com/served/repo.git --walk
Error: --walk runs the filesystem inventory walker, and a Git source has no filesystem to walk (https://example.com/served/repo.git). Read a pinned tree with --api '/api/tree?depth=N', or --walk a local directory.
? 1
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https:/example.com/served/repo.git --walk
walk: repo.git
status: done
counts: files=1 dirs=1 symlinks=0
totals: total_files=1 total_size=7

entries:
  . [dir] files=1 size=7
  served.txt [file] size=7
? 0
```

## Test: a refused ROOT names its reason and nothing else

Every refusal is the one line `Error: invalid ROOT (<reason>)`. One input per reason
would repeat that line, so the fixture holds the reasons and this test holds the cases
where the command line itself matters.

A leading `-` reaches the grammar only past `--`, and is refused where Git or SSH could
read it as an option.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab --no-serve -- '--upload-pack=true'
Error: invalid ROOT (option_like)
? 1
```

Remote-helper syntax, which can run a command, names no folder here.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab 'ext::sh -c true' --no-serve
Error: invalid ROOT (remote_helper_syntax)
? 1
```

An empty argument is refused, not read as the current directory.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab '' --no-serve
Error: invalid ROOT (empty)
? 1
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab http://example.com/owner/repo.git --no-serve
Error: invalid ROOT (unsupported_transport)
? 1
```

A token in the query or in the userinfo does not reach the terminal, in the acquisition
mode or in the route mode.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab 'https://example.com/owner/repo.git?access_token=secret' --no-serve
Error: invalid ROOT (query_not_allowed)
? 1
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=$PWD/home metab https://token123@example.com/owner/repo.git --api /api/cache/sources
Error: invalid ROOT (credentials_in_url)
? 1
```

## Test: no command created the application home

```console
$ test -e home || echo "no application home"
no application home
```
