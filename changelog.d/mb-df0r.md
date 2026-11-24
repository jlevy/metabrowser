- **PDFs open in the browser’s own viewer.** A new built-in `pdf` plugin claims any file
  that starts with `%PDF-`, whatever its name, and any `.pdf`, which until now opened in
  the Bytes view. Its PDF view shows the file in the browser’s viewer, under the same
  sandbox as every raw file.
  Above it, Download saves a copy, and Open in new tab shows it at full size; in the
  macOS app, Open opens it in the app the Mac uses for PDFs, Preview unless you chose
  another. A pinned revision, a GitHub repository, or a folder served `--untrusted` shows
  a note and the same actions in place of the inline viewer, which its content policy
  blocks
  ([the PDF plan](docs/project/specs/active/plan-2026-11-24-pdf-plugin-and-open-in-default-app.md)).

- **Plugin SDK:** `metabrowser.capabilities()` reports the trust profile the page was
  served under, and `metabrowser.host.supports(action)` reports what the page’s host
  does beyond a browser, by action name.
  The macOS app supports `open-file`, which opens an `<a data-metabrowser-open-file>`
  link’s file in its default app ([Plugins](docs/plugins.md)).

- **App contract:** the macOS app takes a plain click on an
  `a[data-metabrowser-open-file]` link to `/raw?path=…`, whose value is `filesystem` or
  `git_revision`, and opens the file in its default app: the file itself in a folder, a
  read-only, quarantined copy of the served bytes for a pinned revision or a repository.
  It defines `window.metabrowserHost` with the action `open-file` in its pages.
  A `metab` without the `pdf` plugin draws no such link, so the app’s
  `MetabRequirement.minimumRelease` is unchanged
  ([Open Links and the Host Descriptor](docs/project/architecture/arch-macos-app.md#open-links-and-the-host-descriptor)).
