- The macOS app now needs `metab` 0.13.0 or later, rather than 0.12.1: the app’s
  contract with `metab` is at the minor release, so a `metab` change the app depends on
  ships in a minor or major release, never a patch
  ([Choosing a Version](docs/publishing.md#choosing-a-version)). A source checkout now
  reports the next minor release as its development version, `0.13.0.devN` rather than
  `0.12.1.devN`, so run `make install` in a checkout the app already uses.
