---
sandbox: true
path:
  - ../../.venv/bin
patterns:
  ROOT_ARG: '\[ROOT\]'
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
before: >-
  mkdir -p filterroot/.git filterroot/notes/deep filterroot/logs filterroot/skipme &&
  printf 'skipme/\n' > filterroot/.gitignore &&
  printf '# Sample\n\nHello.\n' > filterroot/README.md &&
  printf '# Plan\n' > filterroot/notes/deep/plan.md &&
  printf 'line one\nline two\n' > filterroot/logs/run.log &&
  printf '# Vendored\n' > filterroot/skipme/vendor.md &&
  printf '0123456789abcdef0123456789abcdef' > filterroot/blob.bin
---
# Golden tests: walk mode with the nav filter

The nav filter bar asks two questions a tree walk alone does not answer: which folders a
filter leaves standing, and what each surviving folder rolls up to.
Both are decided by `metabrowser.tree_filter` over the whole index, and both are what
these transcripts pin — so the behaviour behind the navigation panel is checked here
rather than by looking at a browser.

The `before` command builds a fixture where every dimension has something to say:
`logs/` holds no Markdown at all, `notes/deep/` holds one two levels down, and `skipme/`
is gitignored.

## Test: a type filter prunes folders with no match and rolls up the rest

`logs/` is absent, not empty: nothing in it matches, so it is not a folder the reader
has any reason to open.
Every folder that remains reports the bytes and the count of its own matches — `notes`
is 7 bytes here, not the size of the directory.

```console
$ metab filterroot --walk --type .md
walk: filterroot
status: done
filter: types=.md
matched: files=3 size=35

entries:
  notes [dir] files=1 size=7
  notes/deep [dir] files=1 size=7
  notes/deep/plan.md [file] size=7
  skipme [dir] files=1 size=11 [gitignored]
  skipme/vendor.md [file] size=11 [gitignored]
  README.md [file] size=17
? 0
```

## Test: dropping gitignored entries removes the folders they were holding up

`skipme/` survived the filter above only because of a gitignored file, so excluding
those has to take the folder with it.

```console
$ metab filterroot --walk --type .md --no-ignored
walk: filterroot
status: done
filter: types=.md ignored=excluded
matched: files=2 size=24

entries:
  notes [dir] files=1 size=7
  notes/deep [dir] files=1 size=7
  notes/deep/plan.md [file] size=7
  README.md [file] size=17
? 0
```

## Test: a size floor keeps only the folders holding something that large

```console
$ metab filterroot --walk --min-size 18
walk: filterroot
status: done
filter: size>=18
matched: files=2 size=50

entries:
  logs [dir] files=1 size=18
  logs/run.log [file] size=18
  blob.bin [file] size=32
? 0
```

## Test: the summary detail level reports the totals without the entries

```console
$ metab filterroot --walk --type .md --detail summary
walk: filterroot
status: done
filter: types=.md
matched: files=3 size=35
? 0
```

## Test: filtering is a property of the tree, not of the walker’s record stream

```console
$ metab filterroot --walk --format json --stream --type .md 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ Invalid value for --type/--age/--min-size/--no-ignored: requires             │
│ --all-at-once; the streaming surface is unfiltered                           │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```
