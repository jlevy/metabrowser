- **App contract:** the macOS app asks
  `metab FOLDER --api '/api/event-log?limit=1' --format json` where Metabrowser’s own
  event log is, for Help > Open Event Log, which opens the newest segment in a window on
  the log’s own folder, even when a folder that holds it is open, and keeps that folder
  out of Open Recent. The route is unchanged, so no `metab` release the app already
  requires needs a change.
  `metab --event-log` opens the same log from a terminal: it names the directory the
  event log is written to as `ROOT`, so serving selects the newest segment, and `--api`,
  `--show`, `--walk`, and `--check-api` read it as a folder.
  A pull request page’s Details names the menu item for a server the app started, from
  `METABROWSER_SETTINGS.EVENT_REPORTS.open_menu`, and the command otherwise, from
  `open_command`. See [Browsing the Log](docs/realtime-debugging.md#browsing-the-log).
