- A pull request’s Diff summary that has not arrived at the late threshold now says so
  in place of its placeholder, and a failed refresh’s line ends the same way, each with
  **Details**: what the server is still running, the failures in the window by cause
  with the message, the addresses that failed, and the latest calls, the last probe of
  GitHub, and the page’s own slow or unfinished work, with links to the records.
  The page reports to the event log what only it saw: a request slower than the
  slow-request threshold or still pending at it, a frame that froze it, and a wait still
  running at the late threshold, and how that wait ended, `never_completed` when the
  reader left first. Every request a page sends to its server’s `/api/` carries the
  page’s client ID in the `x-metabrowser-client` header, which the server’s records of
  the request and of the jobs and processes it starts carry as `client`, so
  `metab . --api '/api/event-log?client=<page>'` reads everything one page asked for and
  saw. `POST /api/event-log/client` is new.
  See [What the Page Reports](docs/realtime-debugging.md#what-the-page-reports).

- For plugin authors: `mb.eventReports`, present once the shell has loaded the
  `event-reports` bundle (`mb.ensureAsset("event-reports")`), names a wait the event log
  hears of if it runs late (`wait(name, {startedAt, detail, onLate})`, ended with
  `end(outcome)`) and paints the Details for a query (`showDetails(panel, query)`).
