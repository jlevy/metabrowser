- `metab --doctor` reports what GitHub work needs from GitHub CLI: the `gh` it found and
  its version, the account it is signed in to, that account’s token scopes, and one
  state (`ok`, `gh_missing`, `gh_too_old`, `not_logged_in`, `missing_scope`,
  `network_error`, or `gh_failed`) with the command or page that fixes it.
  `--doctor --json` carries the same report as `github`, and
  `POST /api/plugin/github/status` serves it to any page or tool.
  The report never changes the doctor’s exit status.
  Opening a pull-request URL now checks it first: when `gh` is missing, too old, or not
  signed in and the pull request is not cached, the command stops with exit status 1 and
  that step, without cloning anything, where it used to clone and then serve the default
  branch. A repository that is not found while the token lacks the `repo` scope now says
  so, with the `gh auth refresh` command that adds it.
