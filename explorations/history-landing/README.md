# History Landing Measurement

This fixture measures what Back does to a page on a pinned revision in stock Chrome.
The page names the commit it was rendered for.
Back brings it back from the back/forward cache, or loads it again from the HTTP cache,
without asking the server, so after a pin switch the page can name a commit the server
no longer serves: its tree answers “Could not load files” and every data request is
refused as `pin_changed`.

Two fixes were measured.
Serving the page `Cache-Control: no-store` makes the browser ask for it again, and keeps
every pin page out of the back/forward cache.
The fix that shipped leaves the page cacheable: `static/source-pin-guard.js` asks
`/api/source/status` once on a history landing and reloads if another commit is served.

## Running It

Build the mirror of `tests/diff_view_file_fixture.py`, serve it, and drive an installed
Chrome over the DevTools protocol, headless and with a throwaway profile:

```shell
QA_VF="$(mktemp -d "${TMPDIR:-/tmp}/mb-history.XXXXXX")"
PYTHONPATH="$PWD" uv --config-file uv.toml run --frozen python -m tests.diff_view_file_fixture "${QA_VF}"
METABROWSER_HOME="${QA_VF}/home" uv --config-file uv.toml run --frozen metab "file://${QA_VF}/origin.git" --no-open --port 8745
# In a second terminal:
node explorations/history-landing/measure.mjs http://127.0.0.1:8745 6ac4c8b5eb94eecbdb621d629b31066f050c75f1 --rounds 10
node explorations/history-landing/measure.mjs http://127.0.0.1:8745 6ac4c8b5eb94eecbdb621d629b31066f050c75f1 --rounds 10 --no-bfcache
```

Each round opens the commit’s diff, scrolls it by 150 pixels, leaves by a View file
control, and comes Back.
`unchanged` leaves by the link, which switches nothing.
`switched` leaves by the button, which switches the served pin first, so each round
lands on a page whose commit is no longer served.
`--no-bfcache` starts Chrome with the back/forward cache off, the path a browser takes
for a page that is not eligible for it.
Times are from `history.back()` to the landing’s `pageshow`, and to the first frame in
which the diff is in the page.

## Recorded Result

Measured on 2026-09-30 in Chrome 152.0.7977.83, headless, on macOS, ten rounds each,
with the machine under other load (a load average near 70).

With the back/forward cache, the page is restored every time (`pageshow.persisted` is
true and `notRestoredReasons` is empty):

| Landing | Back to `pageshow` | Back to the diff | Scroll | Documents loaded | Reloads |
| --- | --- | --- | --- | --- | --- |
| Nothing switched | 3–14 ms | 3–14 ms | kept (150 → 150) | 0 | 0 |
| After a switch | 3–11 ms, then the reload | 204–541 ms | reset | 1 | 1 |

With the back/forward cache off, Back loads the page from the HTTP cache with the
navigation type `back_forward`:

| Landing | Back to `pageshow` | Back to the diff | Scroll | Documents loaded | Reloads |
| --- | --- | --- | --- | --- | --- |
| Nothing switched | 19–29 ms | 170–233 ms | reset | 1 | 0 |
| After a switch | 18–24 ms, then the reload | 185–306 ms | reset | 2 | 1 |

In every round the page ended on the commit the server served, never showed “Could not
load files”, and reloaded at most once.
The landing guard asked the status route once per landing; the freshness row polls the
same route when a page becomes visible, as it did before.

For comparison, the review of the `no-store` header measured Back to the diff in the
same Chrome at 342–630 ms on every landing, switched or not, with the scroll position
lost and `notRestoredReasons` naming `response-cache-control-no-store`, against 8–34 ms
without the header. The landing guard keeps the unchanged case at the cached page’s cost
and pays the reload only when the pin moved.

The desktop app’s browser pane never restores from the back/forward cache, so it
exercises the second table’s path.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
