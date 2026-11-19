- A served Metabrowser writes a structured event log, one JSON line for every request,
  background job, and `git` or `gh` process, with how long it took, how it ended, and
  what started it. Work that never finishes, such as a pull request refresh whose `gh`
  stops answering, is on record within seconds, and a `gh` timeout says where it
  stalled. The log lives under `~/.local/state/metabrowser/events/` (or
  `METABROWSER_STATE_DIR`), bounded in size, and
  `metab . --api '/api/event-log?outcome=timeout,failed'` reads it; see
  [Event Log](docs/realtime-debugging.md#event-log).
