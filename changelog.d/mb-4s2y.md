- The root’s name at the top of the navigation leads with a mark for what is open: a
  cloud for a cloud mirror, a folder with Git’s branch for a local Git checkout, and a
  folder with a dot for a local folder.
  Hover the mark for its kind, such as “Cloud mirror of owner/repo”, “Local Git checkout
  (GitHub: owner/repo)”, or “Local folder”.
  None of them is the plain folder outline of an ordinary folder, and the macOS app
  draws the same three marks, glyph for glyph, in the title’s folder chooser and path
  menu, the Switch Folder panel, File > Open Recent, and the Dock menu; the path menu
  keeps the plain outline for the folders above the root.
  [Source Kinds](docs/design-system-icons.md#source-kinds) lists each mark.
- `GET /api/identity` says a root’s kind as `folder`, `git`, or `mirror`, with
  `kind_label` “Local folder”, “Local Git checkout”, or “Cloud mirror” (a mirror was
  “Cached mirror”), and a new `kind_tip`, the sentence the mark carries as its tooltip.
  A folder is `git` when it holds a `.git` entry, and it stays `git` while it shows one
  of its revisions.
- `metab --recent --json` lists `git` for each target, true for a folder that was a
  checkout when it was opened, so the macOS app can draw its mark without looking at the
  folder. A recent folder opened before this release lists it as false until it is opened
  again.
- **App contract:** the macOS app reads a third value of `kind` from
  `GET /api/identity`, `git`, beside `folder` and `mirror`, and `git` for each target of
  `metab --recent --json`, which it draws each root’s mark from.
  The app and `metab` change together, and `MetabRequirement.minimumRelease` stays
  0.13.0, the release that first has `--recent`.
