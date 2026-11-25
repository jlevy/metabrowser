- The macOS app passes a `METABROWSER_CONFIG_DIR` it was launched with on to every
  `metab` it runs, so `open --env METABROWSER_CONFIG_DIR=DIR -a Metabrowser` keeps that
  launch’s recent targets and `config.yml` in `DIR`, apart from your own.
  The [macOS app hand checks](docs/project/qa/qa-macos-app-hand-checks.md) launch the
  development build this way, so they no longer record their scratch folders in, or
  clear, your own recent list.
  Launched from Finder or the Dock, the app uses the default configuration directory as
  before, unless launchd’s own environment sets one (`launchctl setenv`).

- **App contract:** `ChildEnvironment` passes `METABROWSER_CONFIG_DIR` through, so
  `metab --doctor` keeps it out of `STORAGE_OVERRIDES` and lists it in
  `LAUNCH_STORAGE_OVERRIDES`. Run from the app’s Check Setup…, the doctor takes a
  `METABROWSER_CONFIG_DIR` it sees as the one the app’s servers use and no longer warns
  of it; run in a terminal, which cannot tell what the app was launched with, it still
  warns, since a terminal’s `export` does not reach the app.
  With a `metab` from before this change, an app launched with `METABROWSER_CONFIG_DIR`
  still shows that warning in Check Setup…, wrongly, since its servers do get the
  directory; an app launched without one sees no warning.
