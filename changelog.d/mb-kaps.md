- In the macOS app, a folder opened again just after its last window closed writes the
  folder’s own log, `<folder>-<hash>.log`, again.
  It could instead write `<folder>-<hash>.app-<pid>.log` when the app was starting
  another process at the moment the earlier session let the log go, because the claim on
  the log outlived the session until that process had started.
