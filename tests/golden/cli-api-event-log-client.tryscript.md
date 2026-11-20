---
sandbox: true
path:
  - ../../.venv/bin
env:
  TERM: "dumb"
  TZ: "UTC"
  METABROWSER_PLUGINS_DIRS: ""
  METABROWSER_LOG_LEVEL: "WARNING"
  METABROWSER_EVENT_LOG: "0"
before: >-
  mkdir root &&
  cp "$TRYSCRIPT_TEST_DIR/../fixtures/event-log-client/reports.json"
  "$TRYSCRIPT_TEST_DIR/../fixtures/event-log-client/refused.json"
  "$TRYSCRIPT_TEST_DIR/../fixtures/event-log-client/not-a-page.json"
  "$TRYSCRIPT_TEST_DIR/../fixtures/event-log-client/unknown-field.json" . &&
  install -d -m 700 state state/events &&
  install -m 600
  "$TRYSCRIPT_TEST_DIR/../fixtures/event-log-client/events-20261119T214000Z-p6161-000.jsonl"
  state/events/ &&
  touch -t 202611192141.30 state/events/events-20261119T214000Z-p6161-000.jsonl
---
# Golden tests: what a page reports to the event log, through `--api --data`

A page reports what only it saw to `POST /api/event-log/client`
(`metabrowser.event_log_reports`, sent by `static/event-reports.js`): a request to this
server slower than the slow-request threshold, or still pending at it; a frame that
froze the page; and a wait it shows as loading that is still running at the late
threshold, then how that wait ended, `never_completed` when the reader left first.
Each accepted report becomes one `browser` record, joined to the server’s records by the
page’s client ID: the page’s own (`k3v9q2zx`), or one of its requests’ (`k3v9q2zx-<n>`),
which each request carries in the `x-metabrowser-client` header.

The route takes only the fields it names, of the types and sizes it names, redacts their
text as the server’s own records are, and answers what it wrote.
A one-shot command writes no event log, so `logged` is `false` and `records` shows what
a served process would write.

## Test: a page’s reports, each written as a browser record

A slow request’s end with its Server-Timing, the Diff summary’s wait at the late
threshold and its end when the reader left, and a frozen frame with the script the
browser blamed for it.

```console
$ metab root --api /api/event-log/client --data reports.json
api: /api/event-log/client
status: 200
{
  "accepted": 4,
  "refused": [],
  "rate_limited": 0,
  "dropped_by_page": 0,
  "logged": false,
  "records": [
    {
      "event": "end",
      "kind": "browser",
      "name": "fetch GET /api/plugin/github/pull-files-summary",
      "client": "k3v9q2zx-2",
      "dur_ms": 2500.0,
      "outcome": "ok",
      "attrs": {
        "status": 200,
        "server_ms": 2301.2,
        "threshold_ms": 2000.0,
        "path": "/pull/7"
      }
    },
    {
      "event": "open",
      "kind": "browser",
      "name": "wait githubPull:diffSummary",
      "client": "k3v9q2zx",
      "dur_ms": 10000.0,
      "outcome": null,
      "attrs": {
        "threshold_ms": 10000.0,
        "detail": {
          "number": 7
        },
        "path": "/pull/7"
      }
    },
    {
      "event": "end",
      "kind": "browser",
      "name": "wait githubPull:diffSummary",
      "client": "k3v9q2zx",
      "dur_ms": 61234.5,
      "outcome": "never_completed",
      "attrs": {
        "threshold_ms": 10000.0,
        "detail": {
          "number": 7
        },
        "path": "/pull/7"
      }
    },
    {
      "event": "end",
      "kind": "browser",
      "name": "render blocked",
      "client": "k3v9q2zx",
      "dur_ms": 812.4,
      "outcome": "ok",
      "attrs": {
        "threshold_ms": 500.0,
        "detail": {
          "at_ms": 4322,
          "function": "paintSummaryWait",
          "source": "/static/plugins/github/pull-page.js"
        },
        "path": "/pull/7"
      }
    }
  ]
}
? 0
```

## Test: each report is refused alone, saying why, and text is redacted

A report naming another page’s request, an open report with an outcome, and one with a
field a report does not have are each refused, by index; the rest are written.
A query string the page would never send is still redacted: the token and the
`Authorization` header’s value do not reach the log.
The page’s count of reports it dropped past its own bound is reported back.

```console
$ metab root --api /api/event-log/client --data refused.json
api: /api/event-log/client
status: 200
{
  "accepted": 2,
  "refused": [
    {
      "index": 1,
      "error": "client must be the page's ID or one of its requests'"
    },
    {
      "index": 2,
      "error": "an open report has no outcome"
    },
    {
      "index": 3,
      "error": "attrs.cause is not a field a report has"
    }
  ],
  "rate_limited": 0,
  "dropped_by_page": 3,
  "logged": false,
  "records": [
    {
      "event": "open",
      "kind": "browser",
      "name": "fetch GET /api/plugin/github/pull-comparison",
      "client": "k3v9q2zx-7",
      "dur_ms": 2000.0,
      "outcome": null,
      "attrs": {
        "threshold_ms": 2000.0,
        "path": "/pull/7"
      }
    },
    {
      "event": "end",
      "kind": "browser",
      "name": "fetch GET /api/tree?token=[redacted]",
      "client": "k3v9q2zx",
      "dur_ms": 2400.0,
      "outcome": "failed",
      "attrs": {
        "status": 0,
        "error": "TypeError: Authorization: [redacted]",
        "path": "/pull/7"
      }
    }
  ]
}
? 0
```

## Test: a body that is not a page’s is refused whole

```console
$ metab root --api /api/event-log/client --data not-a-page.json
api: /api/event-log/client
status: 400
{
  "error": "page must be the page's ID: letters and digits",
  "code": "invalid_report"
}
Error: /api/event-log/client returned HTTP 400
? 1
```

```console
$ metab root --api /api/event-log/client --data unknown-field.json
api: /api/event-log/client
status: 400
{
  "error": "spans is not a field of a report's body",
  "code": "invalid_report"
}
Error: /api/event-log/client returned HTTP 400
? 1
```

## Test: the route takes only a POST

```console
$ metab root --api /api/event-log/client
api: /api/event-log/client
status: 405
Method Not Allowed
Error: /api/event-log/client returned HTTP 405
? 1
```

## Test: a page’s ID finds what it asked for and what it saw

The fixture segment is a server whose page `k3v9q2zx` read pull request 7, asked for its
refresh, and waited on its Diff summary.
The refresh job its third request started (`k3v9q2zx-3`) was reported open at 2 s, and
the `gh api` call under it timed out connecting to `20.172.24.160`; the page reported
its wait at 10 s, and that it never completed when the reader left at 61 s, with the
comparison request still pending.
`client=k3v9q2zx` reads all of that, newest first, and nothing of another page’s
(`otherpg1-1`); `client=k3v9q2zx-3` reads one request and the work it started.
Each listing shows a record’s name, client, and outcome, and its event where it is not
an `end`.

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/event-log?client=k3v9q2zx' > page.txt
? 0
```

```console
$ grep -E '^  "matched"|^      "(event|name|client|outcome)": "[^e]' page.txt
  "matched": 8,
      "name": "fetch GET /api/plugin/github/pull-comparison",
      "client": "k3v9q2zx-9",
      "outcome": "never_completed",
      "name": "wait githubPull:diffSummary",
      "client": "k3v9q2zx",
      "outcome": "never_completed",
      "name": "gh api",
      "client": "k3v9q2zx-3",
      "outcome": "timeout",
      "event": "open",
      "name": "wait githubPull:diffSummary",
      "client": "k3v9q2zx",
      "event": "open",
      "name": "checkout._pull_job",
      "client": "k3v9q2zx-3",
      "name": "POST /api/plugin/github/pull-refresh",
      "client": "k3v9q2zx-3",
      "outcome": "ok",
      "event": "start",
      "name": "checkout._pull_job",
      "client": "k3v9q2zx-3",
      "name": "GET /api/plugin/github/pull",
      "client": "k3v9q2zx-1",
      "outcome": "ok",
? 0
```

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/event-log?client=k3v9q2zx-3' > request.txt
? 0
```

```console
$ grep -E '^  "matched"|^      "(event|name|client|outcome)": "[^e]' request.txt
  "matched": 4,
      "name": "gh api",
      "client": "k3v9q2zx-3",
      "outcome": "timeout",
      "event": "open",
      "name": "checkout._pull_job",
      "client": "k3v9q2zx-3",
      "name": "POST /api/plugin/github/pull-refresh",
      "client": "k3v9q2zx-3",
      "outcome": "ok",
      "event": "start",
      "name": "checkout._pull_job",
      "client": "k3v9q2zx-3",
? 0
```

## Test: the failures lead with the server’s cause, and list the page’s reports apart

In the same segment the page’s wait and its comparison request never completed, and the
`gh api` call under the refresh timed out connecting.
That is one failure, seen from two sides: `/api/event-log/failures` counts the server’s
record by its cause, and lists the page’s two reports apart, under `page_reports`, each
with a link that finds it by its segment, kind, client, and name.

```console
$ METABROWSER_STATE_DIR=$PWD/state metab root --api '/api/event-log/failures?since=2026-11-19T21:00:00Z' > failures.txt
? 0
```

```console
$ grep -E '^  "failures"|^      "cause"|^    "count"|^      "never_completed"|"details"' failures.txt
  "failures": 1,
      "cause": "connect_timeout",
          "details": "/api/event-log?file=events-20261119T214000Z-p6161-000.jsonl&span=7"
    "count": 2,
      "never_completed": 2
        "details": "/api/event-log?file=events-20261119T214000Z-p6161-000.jsonl&kind=browser&client=k3v9q2zx-9&name=fetch+GET+%2Fapi%2Fplugin%2Fgithub%2Fpull-comparison"
        "details": "/api/event-log?file=events-20261119T214000Z-p6161-000.jsonl&kind=browser&client=k3v9q2zx&name=wait+githubPull%3AdiffSummary"
? 0
```
