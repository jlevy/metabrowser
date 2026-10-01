# Page Connections Measurement

This fixture measures what a tab’s earlier pages cost the page a reader is on, in stock
Chrome.

Opening an address is a full page load, and the page left behind goes into the
back/forward cache so that Back can show it again at once.
Chrome keeps such a page’s open requests with it.
Every page of a served folder holds one request open for as long as it lives, its
`/api/events` stream, and Chrome opens at most six HTTP/1.1 connections to a host.
So five kept pages and the current page’s own stream use all six, and the sixth page’s
other requests wait until Chrome gives up on a kept page.

The fix that shipped is `createPageConnections` in `static/navigation.js`: a page closes
its event stream, and the live tail of a log, on a `pagehide` that says it is kept, and
opens them again on the `pageshow` that restores it.

## Running It

Serve a folder that has ten files, and drive an installed Chrome over the DevTools
protocol, headless and with a throwaway profile:

```shell
uv --config-file uv.toml run --frozen metab <folder> --no-open --port 8821
# In a second terminal:
node explorations/page-connections/measure.mjs walk http://127.0.0.1:8821 \
  --paths a.md,b.py,c.md,d.json,e.jpg,f.svg,g.html,h.txt,i.jsonl,j.bin --netlog net-log.json
node explorations/page-connections/net-log.mjs net-log.json 127.0.0.1:8821
node explorations/page-connections/measure.mjs back http://127.0.0.1:8821 \
  --paths a.md,b.py,c.md,d.json --away 65000
```

`walk` loads each address as a new document in one tab and reports, for each page, the
time until its preview and tree are in the page and the longest any of its requests
waited before it was sent.
`back` then goes Back through the pages and reports each landing: `pageshow.persisted`,
the time from `history.back()` to `pageshow`, the scroll position, the requests the
landing made, and whether the tree changed.
`mirror` does the same on a served mirror, leaving a commit’s diff by its View file
links. `net-log.mjs` reads Chrome’s own log of its connection pool: which requests
stalled on the six-connection limit, and which requests held the connections then.
`measure.mjs` lists the options.

## Recorded Result

Measured on 2026-10-01 in Chrome 152.0.7977.83, headless, on macOS, against the folder
of section 3.4 of the v0.12 QA runbook.
Before is commit `373b59a9`; after is the fix.
Runs alternate before and after, and the machine was under heavy unrelated load
throughout: the load average is given with each run, and no time here is a clean one.

### The Sixth Page

Ten addresses in one tab, with the back/forward cache on.
Times are in milliseconds, in the order the pages were opened.

| Run | Load average | Ready | Longest wait of a request, pages 2 to 10 |
| --- | --- | --- | --- |
| Before 1 | 195–258 | 1796, 112, 211, 132, 160, **56343**, 455, 581, 235, 274 | 56238 |
| After 1 | 294–299 | 1869, 118, 171, 112, 113, 268, 136, 357, 122, 107 | 4 |
| Before 2 | 249–269 | 2277, 208, 445, 377, 414, **54899**, 912, 500, 366, 269 | 54650 |
| After 2 | 191–200 | 1420, 90, 465, 210, 266, 91, 156, 617, 223, 87 | 12 |
| Before 3 | 187–112 | 1510, 121, 193, 99, 95, **56253**, 202, 367, 102, 304 | 56118 |
| After 3 | 101–100 | 1110, 137, 144, 101, 176, 98, 103, 90, 74, 68 | 6 |
| Before, cache off | 95–91 | 807, 256, 156, 109, 150, 71, 150, 296, 123, 96 | 3 |
| After, cache off | 89–87 | 1467, 177, 201, 195, 129, 201, 90, 300, 105, 94 | 4 |
| 0.11.0, run 1 | 83–99 | 1013, 102, 147, 90, 134, **57060**, 686, 479, 824, 394 | 56838 |
| 0.11.0, run 2 | 106–101 | 799, 100, 150, 110, 107, **56741**, 186, 270, 151, 235 | 56642 |

Before the fix the sixth page was ready after 55 to 56 s in all three runs, and logged
`metabrowser plugin asset failed to load: /plugin-static/image/styles.css (timed out)`
each time. After it no page from the second on had a request wait longer than 12 ms.
The installed 0.11.0 release does what the commit before the fix does, so this is an old
defect and not one the v0.12 work introduced.

The first page of every run is slower because nothing is cached yet.
Its own startup scripts queue for the six connections for 49 to 535 ms, with the cache
on or off, before and after: the net log shows no event stream among the holders.

### What Held the Connections

The net log of Before 1 names the requests that waited and what held the host’s six
sockets when each began to wait:

```text
  t+6.39s  waited  56038 ms  /api/git/repo  (6 of 6 sockets held by event streams)
  t+6.40s  waited  56007 ms  /plugin-static/image/styles.css  (6 of 6 sockets held by event streams)
  t+6.40s  waited  56232 ms  /plugin-static/image/index.js  (6 of 6 sockets held by event streams)
  t+6.40s  waited  56237 ms  /api/catalog  (6 of 6 sockets held by event streams)
  t+6.89s  waited  55753 ms  /api/tree?depth=0  (6 of 6 sockets held by event streams)
```

In the three runs before the fix, the `/api/events` request of each of the first six
pages held its socket for 60.7 to 63.0 s: Chrome evicts a kept page whose request is
still open after a minute, and its connection goes with it.
No other request held a socket for two seconds or longer in any of the ten runs above.
After the fix each stream ends when its page is left, 0.7 to 2.3 s after it opened, and
the only requests that queued for a connection were the first page’s startup scripts and
one `/favicon.ico`.

A page that tails a live log holds a second connection, `/api/stream`. Before the fix it
stayed open while the page was kept; after it, it closes with the event stream and
reopens on the landing from the byte it had reached: the page asked for `cursor=6966`
when it opened and `cursor=8024` when it came back.

### Back

Four pages, then Back three times.
Every landing was restored from the back/forward cache, loaded no document, and kept its
scroll position (120 → 120 on the one page long enough to scroll).

| Run | Load average | Back to `pageshow` (ms) | Requests on each landing |
| --- | --- | --- | --- |
| Before 1 | 107–114 | 18, 11, 12 | none |
| After 1 | 131–145 | 11, 4, 6 | `/api/events`, `/api/catalog`, `/api/tree?depth=0` |
| Before 2 | 154–165 | 21, 50, 49 | none |
| After 2 | 168–166 | 9, 4, 14 | `/api/events`, `/api/catalog`, `/api/tree?depth=0` |
| Before 3 | 156–144 | 7, 10, 17 | none |
| After 3 | 148–136 | 5, 4, 8 | `/api/events`, `/api/catalog`, `/api/tree?depth=0` |

After the fix a landing makes the three requests a reconnect makes: the stream, which
begins with a snapshot; the catalog, which the server answers `304` when nothing
changed; and the root’s totals.
With nothing changed, applying the snapshot rewrote 84 attributes in the tree with the
values they had: the tree’s markup and the whole page’s were identical before and after,
and the layout-shift total was 0.

With a file created after the first landing, that page’s tree gained the row from the
reopened stream, and the two pages restored afterwards, which were away when the file
appeared, gained it from their snapshot.

Chrome fires `pagehide` before `visibilitychange`, and on the way back `resume`,
`visibilitychange`, then `pageshow`. A kept page is frozen, so its timers do not run
while it is away; the freshness row had already stopped its own on `visibilitychange`.
In the two runs after the fix that stayed 65 s on the last page, the net log has no
request at all from three seconds into the stay until the first landing.

### Back After a Minute

The same four pages, with 65 s on the last one before going Back.

| Run | Load average | `persisted` | Back to `pageshow` (ms) | Documents loaded | Requests | Scroll |
| --- | --- | --- | --- | --- | --- | --- |
| Before 1 | 113–115 | false ×3 | 35, 24, 20 | 1, 1, 1 | 75, 52, 83 | 120 → 0 |
| After 1 | 128–117 | true ×3 | 10, 3, 5 | 0, 0, 0 | 3, 3, 3 | 120 → 120 |
| Before 2 | 128–137 | false ×3 | 48, 36, 30 | 1, 1, 1 | 75, 52, 83 | 120 → 0 |
| After 2 | 145–139 | true ×3 | 33, 4, 11 | 0, 0, 0 | 3, 3, 3 | 120 → 120 |

Before the fix Chrome had evicted every kept page by then, and reported why:
`NetworkRequestTimeout`. Back loaded the page again and lost its scroll position.
A page that holds no request stays in the cache, so the fix also makes Back instant
after a minute away, which it was not.

### A Served Mirror

A pin’s page opens no event stream, since a pinned revision has no watcher, so it never
held a connection. Eight rounds of View file and Back from a commit’s diff, twice before
and twice after: every landing restored (`persisted` true), no request of a file’s page
waited longer than 6 ms, and each landing made the same two `/api/source/status`
requests, one from the history-landing check and one from the freshness row.
Back to `pageshow` took 4 to 15 ms before and 3 to 27 ms after, at load averages of 122
to 145.

## What It Does Not Show

Only Chrome was measured, and only headless.
Firefox and Safari have their own rules for which pages they keep, and were not run.
A request still in flight when a page is left is not closed by the page; none held a
connection for two seconds in these runs.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
