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
  A server that serves the folder the log is in writes no log of its own, since each
  request for the files on screen would change one of them.
  See [Browsing the Log](docs/realtime-debugging.md#browsing-the-log).
