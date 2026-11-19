- The macOS app needs `metab` 0.13.0 or later; 0.12.0 is too old.
  A `metab` change the app depends on ships in a new minor or major release, never a
  patch ([Choosing a Version](docs/publishing.md#choosing-a-version)). A source checkout
  reports the next minor release as its development version, `0.13.0.devN`, and
  `make install` or any `uv run` rebuilds that version after each new commit or tag.

- `metab --doctor` checks the setup as well as the plugins: `metab` itself (version,
  Python, how it was installed, and whether the macOS app `--present` would open runs
  it), Git against the floors for cloning and for a partial clone, and the configuration
  and cache directories.
  Each check has a state, details, and the step that fixes it, and `--doctor --json`
  lists them under `checks`
  ([Diagnostics](docs/command-line.md#diagnostics-and-plugins)). A warning never changes
  the exit status; a broken configuration or cache directory exits 1.

- GitHub work needs `gh` 2.81.0 or later.
  `metab --doctor` and the GitHub status route report an older `gh` by its version, with
  `gh_minimum`, and its fix is the upgrade for how `gh` was installed:
  `brew upgrade gh`, `sudo port upgrade gh`, or the install page.

- The macOS app has Help > Check Setup…, which runs `metab --doctor --json` as the app’s
  servers run it and shows each check with its fix, Check Again, and Copy Report;
  Settings’ Run Doctor button is now Check Setup… and opens it
  ([Checking the Setup](docs/macos-app.md#checking-the-setup)). The step that upgrades
  an older `metab` uses the tool that installed it: uv, pipx, or
  `git pull && make install` in a source checkout.
