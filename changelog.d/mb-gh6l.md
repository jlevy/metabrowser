- `metab ROOT --present` opens the target in a browser when no app takes it, and the new
  `open_in` preference chooses: `auto`, the default, uses the app when an installed
  build takes the target and otherwise a browser; `app` uses the app or nothing, exiting
  4 as before; and `browser` never looks for the app.
  `--open-in WHERE` sets it for one command, `METABROWSER_OPEN_IN` for a shell, and
  `open_in` in `config.yml`, a setting `ApplicationConfig` now declares, for good; a
  value that is not one of the three is an `Error:` line naming where it was read.
  For a browser, `--present` starts `metab ROOT` detached, in a session of its own with
  its output in a log in the temporary folder, waits for its `Serving` line and for that
  address to answer `/api/identity` as a server of the target, and reports
  `delivered_to: browser` with the server’s `url`, `pid`, and `log`; the server opens
  the page once it answers and runs until `kill` stops it.
  Its codes are `server_started` and `server_starting` (status 0) and `server_failed`
  (status 1); under `auto` the report’s `fallback` says why no app took the target.
  `present_browser: false` in `config.yml` turns browser delivery off: `--present` then
  opens a target in the app or nowhere, with `browser_off` and status 4. No option of
  the command overrides it, and `--present` refuses `--config-dir`; the environment
  still chooses the configuration directory (`METABROWSER_CONFIG_DIR`,
  `XDG_CONFIG_HOME`, `HOME`), and one without `config.yml` allows a browser.
  Set it with any sandbox rule for `metab --present`, which otherwise lets an agent
  start a server outside the sandbox for any path.
  Every `--present` report gains `open_in`, `open_in_source`, `url`, `pid`, `log`, and
  `fallback`, and `--present --dry-run` adds a `decision`: where the target would go and
  why, looking the app up but sending nothing and starting nothing; its status still
  says only whether ROOT resolved.
  `--app-bundle-id` is now valid with `--dry-run`, and refused with `--open-in browser`.
  `metab --doctor` reports the preference, where it was read, and the app it finds, as
  an `open_in` line and an `open_in` object in `--doctor --json`; an unreadable
  preference, or `app` with no app to take a target, is a problem.
  Bare `metab ROOT` is unchanged and does not read the preference.
  The agent skill gives the user `.url` for a page opened in a browser, adds
  `--open-in browser` for when the user asks for one, stops the server with `kill` when
  the user is done, adds `--open-in app` to every rerun outside the sandbox, and never
  reruns a delivery to a browser there.
  See
  [choosing the app or a browser](docs/command-line.md#choosing-the-app-or-a-browser).
