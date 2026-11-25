---
type: is
id: is-01m8agx0wz8awn1k3qymr3zskn
title: Pulls-stacks Chrome session counts the stack strut as a chip, so its two-stack check can read a page mid-navigation
kind: bug
status: closed
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/856
    at: 2026-11-25T23:43:39.374Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T23:33:22.449Z
updated_at: 2026-11-25T23:51:53.241Z
started_at: 2026-11-25T23:43:37.675Z
closed_at: 2026-11-25T23:51:53.239Z
close_reason: "Fixed in #856 (merge fc20ff03f): the pulls-stacks Chrome session waits for no preview stage, one stack column, and two non-strut chips before reading #10's chips."
resolution: null
duplicate_of: null
---
tests/dom/github-pulls-stacks-chrome.mjs (test_the_pulls_stack_groups_share_the_stack_menus_design_in_chrome) failed once on PR #856's CI, run 45721023624, job chrome (3.14t, 3/4), and passed on the same tests at the previous head (run 45719851528). After clicking Pulls row #10 it waits for document.querySelectorAll('.github-pull-stacks .github-pull-stack-trigger').length === 2 and one frames() pass, then reads the chips. The captured twoStacks was [{text:'3/4', label:'Navigate Stack #286, position 3 of 4'}, {text:'\u00a0', icon:false, label:null}]: #9's chip (#10 is 4/4) and the header's strut. pull-page.js gives the strut (a hidden placeholder that holds the row's height) the class github-pull-stack-trigger too (strut() near line 5098), so the wait's count of 2 is met by a mid-navigation DOM, either #9's view beside #10's strut or a stale chip next to it, before #10's /stacks answer draws its two chips. Fix: wait for two triggers that are not .github-pull-stack-strut and whose labels name #10's positions, or wait on the answer itself, rather than on a count the strut can meet.
