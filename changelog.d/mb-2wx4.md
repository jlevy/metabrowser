- Images from the web now show in a repository you opened from its URL, in a pull
  request’s text, and in a folder served with `--untrusted`, as they do on github.com:
  README badges and screenshots over `https` load, fetched with no referrer sent, where
  they were links to their images.
  An image over `http` is still not loaded.
  A badge that is a link, `[![alt](image)](destination)`, keeps its destination whether
  or not its image loads: the page no longer draws an empty link and a second, visible
  one that went to the image.
  An image that is not loaded is its alt text in a small chip with an image mark, inside
  its link, and its address in the chip’s tooltip.
  **Block remote images**, in the Metabrowser menu and off unless you tick it, turns
  them all into those chips, and the page’s policy then refuses an image from the web,
  so no request for one leaves the page
  ([The Untrusted Page Policy](docs/project/architecture/arch-server-and-content.md#the-untrusted-page-policy)).
  A trusted folder’s own Markdown is unchanged; a pull request’s text, a commit’s, and a
  Markdown diff follow the setting in any folder.
- A link that holds only an image, such as a badge, no longer has a GitHub mark after
  it, in a trusted folder or an untrusted one, so the mark no longer wraps onto a line
  of its own under a row of badges
  ([External GitHub Links](docs/design-system.md#external-github-links)).
