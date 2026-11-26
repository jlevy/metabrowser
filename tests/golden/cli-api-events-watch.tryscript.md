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
  GIT_CONFIG_SYSTEM: "/dev/null"
  GIT_AUTHOR_NAME: "Test"
  GIT_AUTHOR_EMAIL: "test@example.com"
  GIT_COMMITTER_NAME: "Test"
  GIT_COMMITTER_EMAIL: "test@example.com"
  GIT_AUTHOR_DATE: "2020-01-01T00:00:00Z"
  GIT_COMMITTER_DATE: "2020-01-01T00:00:00Z"
before: >-
  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_PREFIX GIT_NAMESPACE GIT_CEILING_DIRECTORIES &&
  mkdir -p watchroot/deep/er &&
  printf 'name,age\nAda,36\nBob,41\n' > watchroot/people.csv &&
  printf 'plain text\n' > watchroot/deep/er/notes.txt &&
  printf '{"path": "people.csv"}\n' > table.json &&
  printf '{"path": "deep/er/notes.txt"}\n' > plain.json &&
  printf '{"path": "gone.csv"}\n' > gone.json &&
  printf '{"connection": "a-closed-stream", "path": "people.csv", "generation": "0123"}\n' > register.json &&
  printf '{"connection": "a-closed-stream", "path": "people.csv", "watch": false}\n' > unregister.json &&
  printf '{"path": "people.csv", "watch": false}\n' > noconnection.json &&
  printf '[]\n' > notobject.json &&
  mkdir checkout &&
  cd checkout &&
  git init -q --initial-branch=main . &&
  printf 'name,age\nAda,36\n' > people.csv &&
  git add -A &&
  git commit -q -m 'first commit' &&
  cd ..
---
# Golden tests: file watches on the event stream

A page holds one `/api/events` stream, and its `fs.snapshot` names the stream’s
connection. An open table, or a container whose children the tree shows, registers its
file on that connection with `POST /api/events/watch`, and the server sends a
`file.changed` on that stream when the file’s generation moves: the table source’s own
generation for a table, and the file’s identity, size, and modification time for any
other path (`metabrowser.file_watches`).

A one-shot `metab` has no stream, so what it reaches is the generation a watch compares,
asked with no connection, and every refusal.
`tests/test_file_watches.py` registers on live connections in process, and
`tests/dom/page-connections-session.js` runs the page’s side.

A generation names a file’s identity and time, which differ from one checkout to the
next, so the transcripts elide it.

## Test: the generation a watch compares

With no connection, nothing is registered: the answer is the generation the watch’s
polls would compare.
A delimited file’s is its table source’s, the one every table read samples.

```console
$ metab watchroot --api /api/events/watch --data table.json
api: /api/events/watch
status: 200
{
  "type": "file_watch",
  "connection": null,
  "path": "people.csv",
  "watching": false,
  "generation": "[..]"
}
? 0
```

```console
$ metab watchroot --api '/api/plugin/table/rows?path=people.csv' > rows.txt
? 0
```

```console
$ grep '"generation"' rows.txt
  "generation": "[..]",
? 0
```

A path deeper than the stream’s tree, which its inventory events never name, is watched
the same way.

```console
$ metab watchroot --api /api/events/watch --data plain.json
api: /api/events/watch
status: 200
{
  "type": "file_watch",
  "connection": null,
  "path": "deep/er/notes.txt",
  "watching": false,
  "generation": "[..]"
}
? 0
```

Nothing readable there is no generation, which a watch reports as a change to `null`.

```console
$ metab watchroot --api /api/events/watch --data gone.json
api: /api/events/watch
status: 200
{
  "type": "file_watch",
  "connection": null,
  "path": "gone.csv",
  "watching": false,
  "generation": null
}
? 0
```

## Test: a connection this process does not hold is refused

A connection id from a stream that ended, or from a server that restarted, is refused
both ways; the page registers again on its next snapshot’s id.

```console
$ metab watchroot --api /api/events/watch --data register.json
api: /api/events/watch
status: 409
{
  "type": "watch_error",
  "code": "unknown_connection",
  "error": "no open event stream has this connection id; register again on the next snapshot's",
  "path": "people.csv"
}
Error: /api/events/watch returned HTTP 409
? 1
```

```console
$ metab watchroot --api /api/events/watch --data unregister.json
api: /api/events/watch
status: 409
{
  "type": "watch_error",
  "code": "unknown_connection",
  "error": "no open event stream has this connection id; register again on the next snapshot's",
  "path": "people.csv"
}
Error: /api/events/watch returned HTTP 409
? 1
```

## Test: a malformed registration is refused

```console
$ metab watchroot --api /api/events/watch --data noconnection.json
api: /api/events/watch
status: 400
{
  "type": "watch_error",
  "code": "bad_request",
  "error": "unregistering needs a connection"
}
Error: /api/events/watch returned HTTP 400
? 1
```

```console
$ metab watchroot --api /api/events/watch --data notobject.json
api: /api/events/watch
status: 400
{
  "type": "watch_error",
  "code": "bad_request",
  "error": "the body is not a JSON object"
}
Error: /api/events/watch returned HTTP 400
? 1
```

## Test: a pinned revision has nothing to watch

A pinned file cannot change, and a pin has no event stream, so the route answers as
`/api/events` does.

```console
$ metab checkout --ref main --api /api/events/watch --data table.json
api: /api/events/watch
status: 409
{
  "error": "This is not available here.",
  "detail": "source does not support watcher",
  "code": "unsupported_for_subject",
  "capability": "watcher"
}
Error: /api/events/watch returned HTTP 409
? 1
```
