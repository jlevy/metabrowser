- The macOS app needs `metab` 0.13.0 or later; 0.12.0 is too old.
  A `metab` change the app depends on ships in a new minor or major release, never a
  patch ([Choosing a Version](docs/publishing.md#choosing-a-version)). A source checkout
  reports the next minor release as its development version, `0.13.0.devN`, and
  `make install` or any `uv run` rebuilds that version after each new commit or tag.

- `metab --doctor` checks the setup as well as the plugins: `metab` itself (version,
  Python, how it was installed, and whether the macOS app `--present` would open runs
  it), Git against the floors for cloning and for a partial clone, and the configuration
  and cache directories.
  A directory that cannot be created is a problem; low free space for a clone, and a
  directory override the macOS app’s servers do not get, are warnings.
  Each check has a state, details, and the step that fixes it, and `--doctor --json`
  lists them, the plugins and `open_in` first, under `checks`
  ([Diagnostics](docs/command-line.md#diagnostics-and-plugins)). A warning never changes
  the exit status; a broken configuration or cache directory exits 1. A configuration
  directory with a problem is listed once, not also under `open_in`.

- Opening a pull request that is not cached needs `gh` 2.81.0 or later, the release that
  added `gh auth status --json`; an older `gh` already stopped there in this release,
  and a public clone or a cached pull request still opens with one.
  `metab --doctor` and the GitHub status route report an older `gh` by its version, with
  `gh_minimum`, and its fix is the upgrade for how `gh` was installed:
  `brew upgrade gh`, `sudo port upgrade gh`, or the install page.
  The status’s new `remedy` gives that fix in the checks’ `{text, command, url}` shape,
  and names a command only for one that runs as written.

- The macOS app has Help > Check Setup…, which runs `metab --doctor --json` as the app’s
  servers run it and shows each check with its fix, Check Again, and Copy Report;
  Settings’ Run Doctor button is now Check Setup… and opens it
  ([Checking the Setup](docs/macos-app.md#checking-the-setup)). The step that upgrades
  an older `metab` uses the tool that installed it: uv, pipx, or
  `git pull && make install` in a source checkout.

- **App contract:** Help > Check Setup… reads `metab --doctor --json`: `ok`, `problems`,
  each entry of `checks` (`id`, `title`, `state`, `summary`, `details[].name` and
  `.value`, and `remedy`’s `text`, `command`, and `url`), and `github`’s `state`,
  `message`, `remedy`, `gh_path`, `gh_version`, `gh_minimum`, and `account`. It sets
  `METABROWSER_DOCTOR_APP` to its own bundle, whose `MetabrowserMinimumMetab` the
  `metab` check compares with.
  The doctor’s configuration and cache checks rely on the app giving its servers none of
  the storage variables (`STORAGE_OVERRIDES` in `cli/doctor.py`).
