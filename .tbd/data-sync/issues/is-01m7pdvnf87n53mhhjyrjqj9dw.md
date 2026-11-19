---
type: is
id: is-01m7pdvnf87n53mhhjyrjqj9dw
title: "macOS app: the view header's GitHub toggle shows github.com for the current item in the window, with a native toggle back to the Metabrowser view"
kind: feature
status: closed
priority: 2
version: 7
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7pac84jxgvafgawtsn1wgn0
hold: null
hold_until: null
created_at: 2026-11-18T04:15:23.623Z
updated_at: 2026-11-19T02:49:00.989Z
started_at: 2026-11-18T22:11:48.623Z
closed_at: 2026-11-19T02:49:00.979Z
close_reason: "Landed in #586 (a36923688), redesigned as the View on GitHub popover per mb-4wqh"
resolution: null
duplicate_of: null
---
Owner, 2026-11-18: "In general, pages should open in the Metabrowser view, but you should always be able to switch to the GitHub view, and then it's simply a web view onto that page on github.com." The coordinator reversed the earlier "no in-app GitHub browser" for the macOS app: in the app (WKWebView), switching the view header's GitHub toggle shows github.com for the current item in that window, and the toggle stays reachable to switch back, so it lives in native window chrome or an overlay that survives showing github.com.

Split from mb-zp7y's web toggle (static/github-page.js, PR stacked on #550), which today opens the item's github.com page in a new browser tab and, in the app, hands it to the default browser (NavigationPolicy.decideNewWindow -> openExternally).

To decide: navigate the window's web view to github.com versus a second WKWebView over it; where the native toggle sits (title-bar accessory beside TitleBarMark, or a toolbar item); how the app learns the item's github.com URL (from the page, e.g. a message from github-page.js's pageUrl, or from metab, e.g. #540's ProviderUrlReducer.web_url); NavigationPolicy for github.com inside that view (stay in-view for github.com, external for others); and the version floor if metab changes (MetabRequirement.minimumRelease). Never sign or notarize.

## Notes

2026-11-18, review A on #552, A9: the macOS title bar's trailing Metabrowser mark is a link that opens the project on GitHub (TitleBarMarkLayout.swift, docs/macos-app.md), while the view header's gray Metabrowser mark just under it is the inert current view, beside a GitHub mark that opens the item's page. Decide here, with the native toggle, what the title-bar mark becomes. Also from the review's design note: the toggle's link carries nothing that tells the app's NavigationPolicy it is the toggle rather than any github.com link, and after #539 a github.com link handed to the app resolves to the Metabrowser view, the inverse direction; write that rule down here. docs/project/qa/qa-macos-app-hand-checks.md item 10 checks today's behavior (the default browser opens the item's page).
Owner, 2026-11-18 (later): the GitHub button should replace the current view with an actual web view on github. We need a way to make sure we maintain persisted cookie state across different tabs, so that once you log into GitHub it stays active. -> One persistent WKWebsiteDataStore shared by every GitHub view in every window and tab, surviving relaunch.
Owner, 2026-11-18 (design, relayed by the coordinator): "We may want to think about how to better have that context preserved, e.g. if there can be a small bar at the top to hold the toggle and we put the web view below it." Then: "We want to be able to switch to the GitHub view, but then go back to our original view as needed." and "But not retain too much clutter if we are in the GitHub view, because that's a whole web page." And, reconfirmed as a must-have: "we want to maintain browser state or cookie logins after a user logs in once."
Design (claude-code@spud10, PR on branch claude/app-github-view): the GitHub view is a second WKWebView below one thin native bar, which holds only the Metabrowser | GitHub toggle at the right (the web header toggle's place and treatment) and a quiet one-line label of the github.com location at the left. The Metabrowser web view stays alive and hidden beside it, so choosing Metabrowser returns to it unchanged; the GitHub view keeps its own page and history across switches. The title bar is unchanged (#575/#578 rework it). The toggle's link carries data-view-toggle="github"; an app user script in its own content world takes a trusted plain click on it and posts the href to a handler the page cannot reach. A github.com link handed to the app (#539) still opens the Metabrowser view; only the toggle opens the GitHub view. One named persistent WKWebsiteDataStore serves every GitHub view in every window and tab and across relaunches; Metabrowser views keep the default store. Metabrowser > Clear GitHub Data… empties it. Not built, a possible later option: following GitHub navigation back into Metabrowser through #539's resolver.
PR jlevy/metabrowser#586 (branch claude/app-github-view, ready, not merged): ShellCore GitHubView/GitHubViewPolicy/GitHubViewState, GitHubViewRequests (content-world click script + handler), GitHubDataStore (named persistent store, fixed UUID), NavigationPolicy.isAppDocument; GitHubPane + bar in the app; View > Show GitHub View (Option-Command-G); Metabrowser > Clear GitHub Data…; File > Open in Default Browser gains Shift-Command-O. github-page.js marks the link data-view-toggle="github" (session check + golden). Tests: GitHubViewTests, GitHubViewWebKitTests (every GitHub view on the same persistent store, never .nonPersistent(); pages keep the default store; cookie shared across GitHub views and not with pages; page cannot reach the handler; scripted click ignored; real click reaches the app, Command-click does not). Hand checks: qa-macos-app-hand-checks.md "The GitHub View" 1-8 (6 = sign in once, then second tab, second window, quit and relaunch). Carries #585's public_hygiene changelog.d exemption hunk byte for byte. For the owner: passkeys/security keys unverified in WKWebView; SAML SSO or third-party sign-in leaves GitHub's domains and opens in the default browser; native toggle colors should follow mb-70d6; PR pages need the marker via toggle(). App not run by hand.
