---
type: is
id: is-01m0nefw4afkt413sm2hh9xaxy
title: Move the Metabrowser wordmark into the gear menu and align the nav header with the file header
kind: feature
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T19:17:18.602Z
updated_at: 2026-08-22T19:46:50.408Z
closed_at: 2026-08-22T19:46:50.408Z
close_reason: Wordmark is the gear menu's title; nav header is one row matching .file-header.
---
Raised in QA: the nav column is the scarcest horizontal space in the app and the wordmark is spending it.

Today, server.py's <header class="app-header"> is three things in a row: <span class="header-brand">Metabrowser</span>, <a class="header-path"> carrying the served path, and .settings-toggle wrapping the gear button and its menu.

Change: drop .header-brand from the header and put 'Metabrowser' at the top of the settings menu as its label, so the gear reads as the Metabrowser menu rather than as an unlabelled settings control. The menu already has .menu-separator to sit the label above.

Then align what remains. The nav header becomes gear + path; the main view header (.file-header) is path + controls, with .file-header-path at --nav-font-size and .file-header-icon for print. Both headers should end up with the same height, the same padding, the same gap between the icon and the path, and the same icon-button size -- so the two columns read as one bar across the top of the app rather than two headers that happen to be adjacent.

Watch the accessible naming: the gear button carries title/aria-label 'Settings' today. If it becomes the Metabrowser menu, that label and the menu's aria-label 'Settings' should be revisited together. Removing the only on-screen instance of the product name also leaves <title>Metabrowser</title> as the sole wordmark on first paint, which is fine but worth a deliberate look.
