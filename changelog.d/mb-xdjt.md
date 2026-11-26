- **Links in rendered text open in Metabrowser.** A pull request’s description,
  comments, reviews, and Guided Review notes, a commit’s message, a Markdown file, and a
  folder’s README now open a `github.com` link into the repository you are browsing in
  Metabrowser whenever it has the same page: the repository’s root, a pull request and
  its Changes and Checks, a commit, the list of pull requests, and a file or folder on
  the branch or commit being browsed.
  A path such as `docs/plan.md` in a pull request’s text, which GitHub resolves to a
  page that does not exist, opens that file at the pull request’s head: in place when
  the head is served, in Changes when the pull request changes the file, and on GitHub
  otherwise. A link in a rendered document in Changes or Docs to another file of the head
  opens it on GitHub when Metabrowser serves another revision, where it was plain text.
  A link to another branch, a tag, an issue, or a comment stays a GitHub link
  ([Links in a Pull Request’s Text](docs/reviewing-pull-requests.md#links-in-a-pull-requests-text)).

- On a mirrored repository, a `github.com` link into the branch being browsed opens in
  the same tab, as a relative link does, rather than in a new one.
