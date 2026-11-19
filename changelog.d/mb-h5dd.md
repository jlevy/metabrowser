- In the macOS app, a GitHub link for a repository you have a checkout of open in a
  window now opens beside it: when the repository’s mirror has no window yet, the mirror
  opens as a new tab of the checkout’s window rather than in a window of its own.
  A checkout is matched by the GitHub repository its `origin` names, not by its folder’s
  name, and of several such windows the one you used most recently takes it
  ([Opening GitHub Links](docs/macos-app.md#opening-github-links)).

- **App contract:** `GET /api/identity` now reports `repository`, the lowercase
  `https://github.com/<owner>/<repo>` a served checkout’s `origin` names or a mirror
  mirrors, or `null` for none on github.com.
  The macOS app reads it to find a checkout of a link’s repository; with a `metab` that
  lacks it, a link’s mirror opens as before.
