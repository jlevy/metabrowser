---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
patterns:
  ROOT_ARG: '\[ROOT\]'
before: >-
  mkdir served && printf 'hello\n' > served/a.txt
---
# Golden tests: serving stops when stdin closes

`--exit-on-eof` is for a parent that holds the server’s stdin open, such as the macOS
app: when that parent exits, even by crashing, the kernel closes the pipe and the server
stops by itself. The watch begins as soon as the command line is read, before startup
does anything that can block.
Here stdin is `/dev/null`, which is at its end from the start, so the server stops with
exit 0 before it serves a request, and almost always before it prints its address;
stdout is dropped so the transcript does not depend on which comes first.
`tests/test_stdin_lifeline.py` closes the stdin of a server that is answering, and of
servers whose startup is held before the banner.

## Test: a closed stdin stops serving

```console
$ metab served --no-open --exit-on-eof < /dev/null 2>&1 >/dev/null
Stopping Metabrowser: stdin closed.
? 0
```

## Test: the flag belongs to serve mode

```console
$ metab served --walk --exit-on-eof 2>&1
Usage: metab [OPTIONS] [ROOT_ARG]
Try 'metab --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ --exit-on-eof not valid with --walk                                          │
╰──────────────────────────────────────────────────────────────────────────────╯
? 2
```
