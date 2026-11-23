- A server left running with no page visible now fetches its mirror every few minutes
  (`STORE_IDLE_REFRESH_S`), so a page opened later is at most that far behind and its
  first ask catches up.
  The fetch is background work: it gives way to anything a reader is waiting for, and
  one that fails is tried again an interval later
  ([Refresh Cadence](docs/project/architecture/arch-mirror-acquisition-and-refresh.md#refresh-cadence)).
