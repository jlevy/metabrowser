- A served Metabrowser writes a structured event log, one JSON line for every request,
  for the background jobs that refresh and prepare what a page shows (pull request and
  file list refreshes, comparison listings, the pull request prefetch, a checkout’s idle
  comparison, GitHub status checks, and repository rediscovery), and for every `git` or
  `gh` process that runs to completion, with how long it took, how it ended, and what
  started it. A streaming `git` session, such as a history or tree reader, is not
  recorded on its own; the request that reads it is.
  Work that never finishes, such as a pull request refresh whose `gh` stops answering,
  is on record within seconds, and a `gh` timeout says where it stalled.
  The log lives under `~/.local/state/metabrowser/events/` (or `METABROWSER_STATE_DIR`),
  bounded in size, and `metab . --api '/api/event-log?outcome=timeout,failed'` reads it;
  see [Event Log](docs/realtime-debugging.md#event-log).
- **App contract:** The macOS app passes `METABROWSER_STATE_DIR`, `XDG_STATE_HOME`, and
  `METABROWSER_EVENT_LOG` from its own environment to the servers it starts, so their
  event log goes where, and only when, those say.
  An older `metab` ignores them.
