---
type: is
id: is-01kzwhmdrhp7q8g25hh0rrz7yh
title: Integrate ARIA tree semantics and focus repair through app render paths
kind: feature
status: closed
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzwhme4gyzm3akfkd83vh2sw
parent_id: is-01kzwhmcj1b9fngz4nj21p1p7e
created_at: 2026-08-13T03:11:12.656Z
updated_at: 2026-08-13T06:29:01.063Z
closed_at: 2026-08-13T06:29:01.062Z
close_reason: Integrated one semantic ARIA tree across root, recent, lazy, paginated, and live-rendered rows; unified pointer and keyboard actions; synchronized focus through every mutation path; and added token-based focus treatment. make verify passes with 927 tests.
---
Integrate the strict navigator into src/metabrowser/static/app.js and styles.css. Extend initKeyboardInfrastructure() with the application-lifetime treeKeyboard handle and extend resolveApplicationFocusFallback() with navigator-based tree-row repair. Add treeRootHtml(), treeDomId(), treeItemAttributes(), treeRootForPanel(), and treeLevelForContainer(); extend renderTreeNodes() and _buildRowHtml() with one role=tree wrapper, role=treeitem/group, aria-labelledby to concise visible names, aria-owns for adjacent non-empty or lazy folder groups, level/position/set metadata for the paged and lazy tree, expanded, selected, tabindex, and keyboard-operable pagination. Known-empty folders remain end nodes without aria-expanded or aria-owns. Preserve page position offsets. Extract setFolderExpanded(), toggleTreeFolder(), mountNextTreePage(), and activateTreeRow() so click and keyboard paths share actions and pagination focus moves into newly mounted content. Bracket and synchronize renderFilesFromTree(), renderRecentFromBase(), loadSubtree(), pagination, filtering, selection, live insertion, animated removal, and type replacement; update findRootReadme(), root insertion, and revealInTree() selectors. Resolve detached tree focus through the navigator and detached preview focus to #preview-pane. Add token-only focus-visible styles and contextual hint activation; leave preview scrolling keys unregistered. Update affected structural tests in test_browser_filter_ui.py and test_browser_v2.py.
