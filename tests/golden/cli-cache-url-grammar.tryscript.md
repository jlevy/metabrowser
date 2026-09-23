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
# Golden tests: the ROOT grammar a user sees

`metab` classifies ROOT before it builds a path or runs Git.
The frozen grammar is `tests/fixtures/repository-cache/url-grammar.json`, and
`tests/test_repository_cache_contract_fixtures.py` replays every case against the
production classifier.
This transcript shows what reaches the terminal: one input per accepted form and per
refusal reason, through the acquisition modes.

No command reaches Git or the network, so this runs as a subprocess on any Git version.
A refused input stops at classification.
An accepted https or ssh source is normalized and then refused by acquisition before Git
runs. An accepted `file://` source is shown through `--walk`, which refuses Git sources
before acquisition; serving or acquiring one needs a Git at or above the floor, so those
sessions are in `tests/test_cli_cache_acquire_golden.py` and
`tests/test_cli_cache_recovery_golden.py`.

A refusal names its reason and never repeats the argument, so a credential or query in a
rejected URL does not reach the terminal.
Every command names an application home in the sandbox, and the last test shows that
none of them created it.

## Test: https sources are normalized, then refused by acquisition

The scheme and host fold to lowercase, the default port and a trailing slash are
dropped, and an encoded unreserved character is decoded.
The path keeps its case.

```console
$ METABROWSER_HOME=$PWD/home metab HTTPS://Example.COM:443/Owner/Repo.git/ --no-serve
Error: https Git sources are not acquired yet (https://example.com/Owner/Repo.git)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://example.com/owner/%72epo.git --no-serve
Error: https Git sources are not acquired yet (https://example.com/owner/repo.git)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab 'https://[2001:DB8::1]:8443/repo.git' --no-serve
Error: https Git sources are not acquired yet (https://[2001:db8::1]:8443/repo.git)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://example.com/owner/repo.git --api /api/cache/sources
Error: https Git sources are not acquired yet (https://example.com/owner/repo.git)
? 1
```

## Test: ssh URLs and scp-like addresses are ssh sources

The default port 22 is dropped and the host folds to lowercase.
An ssh URL keeps a trailing slash and an scp-like address keeps its path as written,
because a generic Git host may interpret either one.
An scp-like address needs a user; without one it is a local path, as a later test shows.

```console
$ METABROWSER_HOME=$PWD/home metab ssh://git@Example.com:22/owner/repo.git --no-serve
Error: ssh Git sources are not acquired yet (ssh://git@example.com/owner/repo.git)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab ssh://git@example.com/owner/repo.git/ --no-serve
Error: ssh Git sources are not acquired yet (ssh://git@example.com/owner/repo.git/)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab git@EXAMPLE.com:Owner/Repo.git --no-serve
Error: ssh Git sources are not acquired yet (git@example.com:Owner/Repo.git)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab git@example.com:owner/repo.git --api /api/cache/layout
Error: ssh Git sources are not acquired yet (git@example.com:owner/repo.git)
? 1
```

## Test: file sources name this machine

`localhost` folds to the empty authority, and a trailing slash is dropped.

```console
$ METABROWSER_HOME=$PWD/home metab FILE://LocalHost/srv/git/repo.git/ --walk
Error: --walk runs the filesystem inventory walker, and a Git source has no filesystem to walk (file:///srv/git/repo.git). Read a pinned tree with --api '/api/tree?depth=N', or --walk a local directory.
? 1
```

## Test: a bare path is never a clone origin

A path, including one that looks like a host and path without a user, stays a local
path, and `--no-serve` has nothing to acquire.

```console
$ METABROWSER_HOME=$PWD/home metab /srv/git/repo.git --no-serve
Error: ROOT is a local path; --no-serve acquires a file:// Git source
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab example.com:owner/repo.git --no-serve
Error: ROOT is a local path; --no-serve acquires a file:// Git source
? 1
```

## Test: arguments that could become Git or SSH options

A leading `-` is refused wherever Git or SSH could read it as an option.
The first command passes `--` so the argument reaches the grammar instead of the option
parser.

```console
$ METABROWSER_HOME=$PWD/home metab --no-serve -- '--upload-pack=true'
Error: invalid ROOT (option_like)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab 'ssh://-oProxyCommand=true/repo.git' --no-serve
Error: invalid ROOT (option_like)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab 'git@example.com:-oProxyCommand=true' --no-serve
Error: invalid ROOT (option_like)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab 'ext::sh -c true' --no-serve
Error: invalid ROOT (remote_helper_syntax)
? 1
```

## Test: transports and malformed URLs

```console
$ METABROWSER_HOME=$PWD/home metab '' --no-serve
Error: invalid ROOT (empty)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab http://example.com/owner/repo.git --no-serve
Error: invalid ROOT (unsupported_transport)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab git://example.com/owner/repo.git --no-serve
Error: invalid ROOT (unsupported_transport)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab git+ssh://example.com/owner/repo.git --no-serve
Error: invalid ROOT (unsupported_transport)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https:/example.com/owner/repo.git --no-serve
Error: invalid ROOT (malformed_url)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab file:srv/git/repo.git --no-serve
Error: invalid ROOT (malformed_url)
? 1
```

## Test: characters no repository address contains

```console
$ METABROWSER_HOME=$PWD/home metab 'https://example.com/owner/my repo.git' --no-serve
Error: invalid ROOT (control_or_whitespace)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://example.com/owner/repo%0A.git --no-serve
Error: invalid ROOT (control_or_whitespace)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://exämple.com/owner/repo.git --no-serve
Error: invalid ROOT (non_ascii)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab 'https://example.com\owner\repo.git' --no-serve
Error: invalid ROOT (backslash)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab 'https://example.com/owner/repo.git?access_token=secret' --no-serve
Error: invalid ROOT (query_not_allowed)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab 'https://example.com/owner/repo.git#readme' --no-serve
Error: invalid ROOT (fragment_not_allowed)
? 1
```

## Test: credentials, users, hosts, and ports

```console
$ METABROWSER_HOME=$PWD/home metab https://alice:secret@example.com/owner/repo.git --no-serve
Error: invalid ROOT (credentials_in_url)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://token123@example.com/owner/repo.git --api /api/cache/sources
Error: invalid ROOT (credentials_in_url)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab ssh://git:secret@example.com/owner/repo.git --no-serve
Error: invalid ROOT (credentials_in_url)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab 'ssh://al;ce@example.com/owner/repo.git' --no-serve
Error: invalid ROOT (invalid_user)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https:///owner/repo.git --no-serve
Error: invalid ROOT (missing_host)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://exa_mple.com/owner/repo.git --no-serve
Error: invalid ROOT (invalid_host)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://example.com:0443/owner/repo.git --no-serve
Error: invalid ROOT (invalid_port)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab file://fileserver/share/repo.git --no-serve
Error: invalid ROOT (file_authority_not_local)
? 1
```

## Test: paths that name no repository or an ambiguous one

```console
$ METABROWSER_HOME=$PWD/home metab https://example.com/ --no-serve
Error: invalid ROOT (missing_repository_path)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab git@example.com: --no-serve
Error: invalid ROOT (missing_repository_path)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://example.com/owner//repo.git --no-serve
Error: invalid ROOT (empty_path_segment)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://example.com/owner/%2e%2e/repo.git --no-serve
Error: invalid ROOT (dot_segment)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab file:///srv/git/./repo.git --no-serve
Error: invalid ROOT (dot_segment)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://example.com/owner%2Frepo.git --no-serve
Error: invalid ROOT (encoded_delimiter)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab https://example.com/owner/repo%zz.git --no-serve
Error: invalid ROOT (invalid_percent_encoding)
? 1
```

```console
$ METABROWSER_HOME=$PWD/home metab 'https://example.com/owner/repo<.git' --no-serve
Error: invalid ROOT (invalid_path_character)
? 1
```

## Test: no command created the application home

```console
$ test -e home || echo "no application home"
no application home
```
