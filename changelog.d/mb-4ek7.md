- **Every folder opens in a window of its own in the macOS app.** File > Open Folder…,
  Open URL…, Open Recent, the Dock, Finder, `metab --present`, and the folder chooser
  each give a newly opened folder its own window, and Command-click opens a new window
  of the same folder. A window never becomes a tab: Settings > General no longer has Open
  folders in, Window > Merge All Windows and the tab bar are gone, and System Settings’
  “Prefer tabs when opening documents” no longer applies.
  A repository’s mirror opens in its own window too, rather than as a tab of an open
  checkout’s window. A window that an earlier version saved with several folder tabs
  comes back at the next launch as a window per folder
  ([Windows](docs/macos-app.md#windows)).

- **App contract:** the macOS app no longer reads `repository` from `/api/identity`,
  which it used only to put a mirror’s window in a tab beside an open checkout.
  The route still answers it, so the app’s `MetabRequirement.minimumRelease` is
  unchanged.
