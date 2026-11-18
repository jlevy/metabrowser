---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
  METABROWSER_RECORD_RECENT: "1"
patterns:
  TIMESTAMP: '\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z'
  ROOTS: '[^\s"]+/roots'
  ROOT_ARG: '\[ROOT\]'
before: >-
  mkdir -p roots/alpha roots/beta roots/gamma/sub roots/leaving &&
  printf 'note\n' > roots/gamma/sub/note.txt
---
# Golden tests: recent targets

`metab` keeps one list of the folders and repositories opened lately, which the macOS
app’s File > Open Recent draws from `metab --recent --json`. These transcripts pin what
is in the list and in what order: the most recently opened first, one entry for each
root, a file standing for its folder and a URL for its repository, and what a damaged
file or one from a newer release lists as.
`tests/test_recent_targets.py` covers the store itself: the cap, writers at once, and
that a real serve records its root.

Each command names its configuration directory with `METABROWSER_CONFIG_DIR`, because
the list lives beside `config.yml` and the frontmatter cannot name the sandbox.
Times are elided; the folders are under `roots/` in the sandbox.

## Test: nothing has been opened yet

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent
No recent targets.
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent --json
{
  "limit": 50,
  "targets": [],
  "problem": null
}
? 0
```

Listing creates nothing:

```console
$ ls -d config 2>/dev/null | wc -l | tr -d ' '
0
? 0
```

## Test: a folder, a file, and a URL are recorded as their roots

A file stands for the folder that serving it would serve, and a pull request’s URL for
its repository, lower-cased as the URL grammar normalizes it.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab roots/alpha --recent-add
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab roots/beta --recent-add
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab roots/gamma/sub/note.txt --recent-add
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab https://github.com/JLevy/TBD/pull/12 --recent-add
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent
mirror  [TIMESTAMP]  https://github.com/jlevy/tbd
folder  [TIMESTAMP]  [ROOTS]/gamma/sub
folder  [TIMESTAMP]  [ROOTS]/beta
folder  [TIMESTAMP]  [ROOTS]/alpha
? 0
```

## Test: opening a root again moves its one entry to the front

`roots/./alpha/` is the same folder, and another URL into the repository is the same
repository.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab roots/./alpha/ --recent-add
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab https://github.com/jlevy/tbd/tree/main/docs --recent-add
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent --json
{
  "limit": 50,
  "targets": [
    {
      "mode": "mirror",
      "root": "https://github.com/jlevy/tbd",
      "opened_at": "[TIMESTAMP]"
    },
    {
      "mode": "folder",
      "root": "[ROOTS]/alpha",
      "opened_at": "[TIMESTAMP]"
    },
    {
      "mode": "folder",
      "root": "[ROOTS]/gamma/sub",
      "opened_at": "[TIMESTAMP]"
    },
    {
      "mode": "folder",
      "root": "[ROOTS]/beta",
      "opened_at": "[TIMESTAMP]"
    }
  ],
  "problem": null
}
? 0
```

## Test: the file is YAML with its format first

```console
$ cat config/recent-targets.yml
# Metabrowser's recent targets: the folders and repositories opened lately, newest
# first. metab writes this file as it serves; `metab --recent` lists it.
format: mf01
targets:
- mode: mirror
  root: https://github.com/jlevy/tbd
  opened_at: '[TIMESTAMP]'
- mode: folder
  root: [ROOTS]/alpha
  opened_at: '[TIMESTAMP]'
- mode: folder
  root: [ROOTS]/gamma/sub
  opened_at: '[TIMESTAMP]'
- mode: folder
  root: [ROOTS]/beta
  opened_at: '[TIMESTAMP]'
? 0
```

```console
$ ls config
recent-targets.lock
recent-targets.yml
? 0
```

## Test: forgetting a target

A URL forgets its repository, and a folder that is gone is forgotten by its path.

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab https://github.com/jlevy/tbd --recent-forget
Forgotten.
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab roots/leaving --recent-add
? 0
```

```console
$ rmdir roots/leaving
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent
folder  [TIMESTAMP]  [ROOTS]/leaving
folder  [TIMESTAMP]  [ROOTS]/alpha
folder  [TIMESTAMP]  [ROOTS]/gamma/sub
folder  [TIMESTAMP]  [ROOTS]/beta
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab $PWD/roots/leaving --recent-forget
Forgotten.
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab roots/beta --recent-forget
Forgotten.
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab roots/beta --recent-forget
Not a recent target; nothing changed.
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent
folder  [TIMESTAMP]  [ROOTS]/alpha
folder  [TIMESTAMP]  [ROOTS]/gamma/sub
? 0
```

## Test: what cannot be a recent target

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab roots/nowhere --recent-add 2>&1
Error: [ROOTS]/nowhere is not a directory
? 1
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab ssh://git@example.com/team/project.git --recent-add 2>&1
Error: ssh Git sources are not served yet (ssh://git@example.com/team/project.git), so they are not recent targets
? 1
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab https://user:secret@github.com/jlevy/tbd --recent-add 2>&1
Error: invalid ROOT (credentials_in_url): the URL carries credentials
? 1
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent
folder  [TIMESTAMP]  [ROOTS]/alpha
folder  [TIMESTAMP]  [ROOTS]/gamma/sub
? 0
```

## Test: a process told not to record

`METABROWSER_RECORD_RECENT=0` is for a server nobody opened to read, such as a
benchmark’s or one the macOS app restores: it records nothing, and neither does
`--recent-add`. The list can still be read and changed.

```console
$ METABROWSER_RECORD_RECENT=0 METABROWSER_CONFIG_DIR=$PWD/config metab roots/beta --recent-add 2>&1
Not recorded: METABROWSER_RECORD_RECENT is off.
? 0
```

```console
$ METABROWSER_RECORD_RECENT=0 METABROWSER_CONFIG_DIR=$PWD/config metab --recent
folder  [TIMESTAMP]  [ROOTS]/alpha
folder  [TIMESTAMP]  [ROOTS]/gamma/sub
? 0
```

## Test: the modes’ usage errors

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent-add 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ ROOT is required for --recent-add; e.g. `metab . --recent-add`               │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab roots/alpha --recent 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ ROOT is not used with --recent                                               │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent --recent-clear 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ mode flags are mutually exclusive; got --recent and --recent-clear           │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab roots/alpha --recent-forget --json 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ --json not valid with --recent-forget                                        │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```

## Test: a file from a newer release is left alone

```console
$ cp config/recent-targets.yml kept.yml && printf 'format: mf02\ntargets: []\nlater: true\n' > config/recent-targets.yml
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent 2>&1
The recent targets file uses format mf02, and this release reads formats up to mf01. Upgrade Metabrowser to list or record recent targets.
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent --json
{
  "limit": 50,
  "targets": [],
  "problem": "The recent targets file uses format mf02, and this release reads formats up to mf01. Upgrade Metabrowser to list or record recent targets."
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab roots/alpha --recent-add 2>&1
Error: not recorded: the recent targets file uses format mf02, and this release reads formats up to mf01. Upgrade Metabrowser to list or record recent targets
? 1
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent-clear 2>&1
Error: the recent targets file uses format mf02, and this release reads formats up to mf01. Upgrade Metabrowser to list or record recent targets
? 1
```

```console
$ cat config/recent-targets.yml
format: mf02
targets: []
later: true
? 0
```

## Test: a damaged file lists as empty, and the next record replaces it

```console
$ printf 'format: mf01\ntargets:\n- mode: folder\n  root: not/absolute\n  opened_at: never\n' > config/recent-targets.yml
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent 2>&1
The recent targets file is damaged (entry 1 cannot be a target: a folder's root is an absolute path), so nothing is listed; the next folder or repository opened replaces it.
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent --json
{
  "limit": 50,
  "targets": [],
  "problem": "The recent targets file is damaged (entry 1 cannot be a target: a folder's root is an absolute path), so nothing is listed; the next folder or repository opened replaces it."
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab roots/beta --recent-add 2>&1
replacing the recent targets file, which is damaged: entry 1 cannot be a target: a folder's root is an absolute path
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent
folder  [TIMESTAMP]  [ROOTS]/beta
? 0
```

## Test: clearing a damaged file replaces it

```console
$ printf 'format: mf01\ntargets: nonsense\n' > config/recent-targets.yml
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent-clear 2>&1
replacing the recent targets file, which is damaged: its targets are not a list
Cleared 0 recent targets.
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent
No recent targets.
? 0
```

## Test: a field this release does not know is kept

A later release may add a field to an entry under the same format.
This one lists the entry by what it knows and carries the field through a rewrite.

```console
$ printf 'format: mf01\ntargets:\n- mode: mirror\n  root: https://github.com/jlevy/tbd\n  opened_at: 2026-11-18T03:14:15Z\n  target: https://github.com/jlevy/tbd/pull/12\n' > config/recent-targets.yml
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent --json
{
  "limit": 50,
  "targets": [
    {
      "mode": "mirror",
      "root": "https://github.com/jlevy/tbd",
      "opened_at": "[TIMESTAMP]"
    }
  ],
  "problem": null
}
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab roots/beta --recent-add 2>&1
? 0
```

```console
$ grep -c 'target: https://github.com/jlevy/tbd/pull/12' config/recent-targets.yml
1
? 0
```

## Test: a mode or a key this release does not know is a newer release’s

It is left alone whatever format it names, so a release that forgot to raise the format
costs no list.

```console
$ printf 'format: mf01\ntargets:\n- mode: remote\n  root: host:/srv/files\n  opened_at: 2026-11-18T03:14:15Z\n' > config/recent-targets.yml
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent 2>&1
The recent targets file holds a mode this release does not know, as a newer release's would. Upgrade Metabrowser to list or record recent targets.
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab roots/beta --recent-add 2>&1
Error: not recorded: the recent targets file holds a mode this release does not know, as a newer release's would. Upgrade Metabrowser to list or record recent targets
? 1
```

```console
$ cat config/recent-targets.yml
format: mf01
targets:
- mode: remote
  root: host:/srv/files
  opened_at: 2026-11-18T03:14:15Z
? 0
```

```console
$ rm config/recent-targets.yml
? 0
```

## Test: clearing the list

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab roots/alpha --recent-add
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent-clear
Cleared 1 recent target.
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent-clear
Cleared 0 recent targets.
? 0
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab --recent --json
{
  "limit": 50,
  "targets": [],
  "problem": null
}
? 0
```

## Test: a setting that names no directory is refused in one line

```console
$ METABROWSER_CONFIG_DIR=relative/config metab --recent 2>&1
Error: METABROWSER_CONFIG_DIR must be a nonempty absolute path without '..' components
? 1
```

```console
$ METABROWSER_CONFIG_DIR=relative/config metab roots/alpha --recent-add 2>&1
Error: not recorded: METABROWSER_CONFIG_DIR must be a nonempty absolute path without '..' components
? 1
```

## Test: a configuration directory other users can read is refused

The list names the user’s folders, so it is read only from a directory that is private
to them, and a listing never changes the directory’s mode to make it so.

```console
$ chmod 755 config && METABROWSER_CONFIG_DIR=$PWD/config metab --recent 2>&1
Error: The Metabrowser storage directory is accessible to other users (mode 0755). Run chmod 700 on it, or set the applicable override (METABROWSER_CACHE_DIR or METABROWSER_CONFIG_DIR) to a private directory you own.
? 1
```

```console
$ METABROWSER_CONFIG_DIR=$PWD/config metab roots/alpha --recent-add 2>&1
Error: not recorded: The Metabrowser storage directory is accessible to other users (mode 0755). Run chmod 700 on it, or set the applicable override (METABROWSER_CACHE_DIR or METABROWSER_CONFIG_DIR) to a private directory you own.
? 1
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
