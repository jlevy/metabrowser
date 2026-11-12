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
  # The sandbox's absolute path, the port the walk found free, and a checkout's
  # `[dev build: …]` suffix all change from run to run.
  SERVED: '/[^ ]+'
  PORT: '\d+'
  BUILD: '(  \[dev build: [^\]]*\])?'
before: >-
  mkdir served && printf 'hello\n' > served/a.txt
---
# Golden tests: serving stops when stdin closes

`--exit-on-eof` is for a parent that holds the server’s stdin open, such as the macOS
app: when that parent exits, even by crashing, the kernel closes the pipe and the server
stops by itself. Here stdin is `/dev/null`, which is at its end from the start, so the
server prints its banner, sees the end, and stops with exit 0 before it serves a
request. `tests/test_stdin_lifeline.py` closes the stdin of a server that is answering.

## Test: a closed stdin stops serving

```console
$ metab served --no-open --exit-on-eof < /dev/null 2>&1
Serving [SERVED] at http://127.0.0.1:[PORT]/view/[BUILD]
Plugins: agent-log, binary, diff, folder, github, html, image, markdown, structured, text, unknown-jsonl
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
