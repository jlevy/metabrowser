- **Open in the macOS app names a copy by its type.** For a pinned revision or a GitHub
  repository, Open’s copy of a file whose name has no extension, or another type’s,
  takes the extension of the type the server sends, so a PDF named `untitled` opens in
  Preview as `untitled.pdf` instead of being refused.
  A type Metabrowser does not open, such as a page or a script, never renames a copy.

- **Open saves to Downloads where no app opens the file.** When no app on the Mac is
  assigned to a file’s type, Open saves a copy in Downloads, under a new name if one is
  taken, and says so with Show in Finder, instead of an Open failed alert.
  The first such save asks once for access to Downloads.

- **App contract:** the macOS app names an Open link’s downloaded copy by the
  `Content-Type` that `/raw` answers, which for a name that gives no type is the type
  the file’s leading bytes give.
  An older `metab` answers such a file as `application/octet-stream`, whose copy keeps
  its name and is refused as before, so the app’s `MetabRequirement.minimumRelease` is
  unchanged
  ([Open Links and the Host Descriptor](docs/project/architecture/arch-macos-app.md#open-links-and-the-host-descriptor)).
