- In the macOS app, Edit > Find (Command-F) works on every page.
  The find bar used to search through AppKit’s text finder, which found nothing on a
  Metabrowser page; it now runs WebKit’s own find, which searches the whole page as a
  browser’s does, including after you open another file in place.
  Return and Command-G find the next match, Shift-Return and Shift-Command-G the
  previous one, Command-E uses the selection, and Escape closes the bar.
