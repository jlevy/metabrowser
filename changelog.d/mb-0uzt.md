- **Links to commits, the pull request list, and other pull requests open in place.** A
  plain click on a link in a Markdown file, a folder’s README, a pull request’s or a
  stack’s text, a commit’s message, or a rendered diff that names a commit’s page, the
  list of pull requests, or another pull request now opens that page in the app, with
  its tab in front and its row revealed, instead of loading the page again and losing
  the app’s state. A modified or middle click still opens the link as the browser does.

- **Plugin SDK:** `metabrowser.navigation.openRoute(href)` opens an in-app page other
  than a file’s in place by the address a link to it carries, `/pull/…`, `/stack/…`,
  `/pulls`, or `/commit/…`, and answers whether it did, so a plugin leaves the click to
  the browser when it answers `false`
  ([Data and Navigation](docs/plugins.md#data-and-navigation)). The method is additive,
  so `PLUGIN_SDK_VERSION` is unchanged.
