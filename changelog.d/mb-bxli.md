- The macOS app needs `metab` 0.13.0 or later; 0.12.0 is too old.
  A `metab` change the app depends on ships in a new minor or major release, never a
  patch ([Choosing a Version](docs/publishing.md#choosing-a-version)). A source checkout
  reports the next minor release as its development version, `0.13.0.devN`, and
  `make install` or any `uv run` rebuilds that version after each new commit or tag.
