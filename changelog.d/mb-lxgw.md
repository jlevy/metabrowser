- In the macOS app, the view header’s GitHub mark shows the item’s page on github.com in
  the window itself, below a thin bar that holds the same toggle with GitHub pressed,
  where it used to open the default browser.
  Choosing Metabrowser shows the page again as you left it, scroll and state included,
  and the GitHub view keeps its own page and history while you switch back and forth.
  View > Show GitHub View, Option-Command-G, switches either way; Back, Forward, Reload
  Page, zoom, Find, Print, and File > Open in Default Browser, now Shift-Command-O, act
  on the view shown. A Command-click on the mark still opens the default browser, and a
  GitHub link sent to the app still opens Metabrowser’s view of it.
  The macOS app guide’s The GitHub View section has the details.

- In the macOS app, signing in to github.com in a GitHub view holds in every window and
  tab and after a relaunch: every GitHub view shares one persistent store of its own,
  apart from Metabrowser’s pages and your browser.
  Metabrowser > Clear GitHub Data… signs you out and removes what github.com stored.

- The view header’s GitHub link carries `data-view-toggle="github"`, the mark by which
  the macOS app knows the toggle from any other link to github.com.
