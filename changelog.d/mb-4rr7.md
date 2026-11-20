- Metabrowser’s own event log opens in Metabrowser.
  A file named `events-*.jsonl`, such as a segment of the log a served `metab` writes to
  its state directory, is an event log, and opens as Timeline (spans nested under the
  spans that started them: a request, the job it started, the `git` and `gh` processes
  the job ran), Latency (the slowest spans and the distribution of every span’s time),
  By kind (each kind and name counted, timed, and ended), and Errors (failures by cause
  as `/api/event-log/failures` groups them, the page’s reports apart, and the work that
  had not ended when the log did), beside Raw JSON, with keys `V`, `L`, `B`, `E`, and
  `S`. Chips choose the kind and the outcome and a menu the least time.
  Each view is a route, `metab DIR --api '/api/plugin/event-log/timeline?path=<file>'`
  and its `slowest`, `kinds`, and `errors`, so a terminal reads what the page shows.
  A server whose folder holds the log, such as `metab ~`, writes its log as usual and
  leaves out the requests for the log itself; one whose folder is the log’s own writes
  none, and says so in its Details and in `metab --doctor`, which now checks the event
  log too. See [Browsing the Log](docs/realtime-debugging.md#browsing-the-log).
- **App contract:** `metab --doctor --json` lists one more check, `event_log`, in
  `checks` (whether a server writes the event log, where, and what it leaves out), which
  Help > Check Setup… shows as a row of its own, since the app draws every entry of
  `checks` it receives.
  No release the app already requires needs a change: an older `metab` lacks the row,
  and the app does not look for it.
