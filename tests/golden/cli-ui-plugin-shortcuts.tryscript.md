---
cwd: ../..
sandbox: false
env:
  TZ: "UTC"
---
# Golden Test: The Plugin Shortcut Surface

A plugin view gives one of its controls a letter key and a badge with
`metabrowser.shortcuts.attach(element, {id, key, group, order, copy, activate, signal})`.
Plugin code can run before the shortcut registry exists, which arrives in the on-demand
`shell-tools` bundle and is rebuilt after a real `pagehide`, so the eager SDK queues
each attachment and the facade, `static/plugin-shortcuts.js`, takes the queue as it
loads and replays every attachment onto each registry the shell attaches.

This browserless session loads the production SDK and its startup prerequisites, the
registry, the overlay layer, Help, the facade, and view composition whole, in the
shell’s order. It plays a plugin view’s controls and the shell around them: the registry
the shell builds and rebuilds, a shell view tab that holds a letter, the inert stage of
a retained navigation, and the reveal that holding Shift turns on.
Each step prints the plugin keys the registry holds, with what each runs on now, every
control’s `aria-keyshortcuts`, the badges while revealed, what the controls were asked
to do, and what the facade warned or logged.

The steps show an attachment queued, detached, and retargeted before the facade loads;
the replay onto the shell’s registry; a key with and without Shift; the badges; Help,
opened through the real overlay, still listing the keys of controls it made inert; the
shell’s reserved letters refused with one warning per command id, and every letter tried
to show the refused set is exactly the reserved table; two plugins on one letter, where
the earlier attachment runs and badges and the later is warned; a shell view tab
outranking a plugin key; two mounts of one command id; a rebuilt control retargeted; a
control taken out of the page and put back; the inert stage; an aborted signal and an
idempotent detach; malformed input, which throws with the `shortcuts.attach:` prefix;
the registry torn down and rebuilt; and view composition releasing a key that a view’s
own `dispose()` forgot, whether or not the facade had loaded, including one whose
`dispose()` takes its own root out of the container, a render that finishes after its
stage was cancelled, and a render that attaches a key and then fails.
`tests/test_keymap.py` holds the printed reserved table and refused letters to
`src/metabrowser/keymap.py`.

```console
$ node tests/dom/plugin-shortcuts-session.js
{
  "steps": [
    {
      "step": "attached before the facade loads: the SDK queues each one",
      "keys": [],
      "aria": ["Unified: none","Stale: none","Before: none","After: none"],
      "queued": 4
    },
    {
      "step": "the facade loads and takes the queue; the malformed one is logged",
      "keys": [],
      "aria": ["Unified: none","Stale: none","Before: none","After: none"],
      "queued": 0,
      "errors": ["shortcuts.attach: the element needs an HTMLElement"]
    },
    {
      "step": "the shell's registry: the queue's keys are replayed onto it",
      "keys": ["L plugin.demo.layout: Unified","M plugin.demo.moved: After"],
      "aria": ["Unified: L","Stale: none","Before: none","After: M"]
    },
    {
      "step": "L runs the control's own activation",
      "keys": ["L plugin.demo.layout: Unified","M plugin.demo.moved: After"],
      "aria": ["Unified: L","Stale: none","Before: none","After: M"],
      "handled": true,
      "did": ["demo.layout ran for the first view's layout"]
    },
    {
      "step": "Shift does not change it",
      "keys": ["L plugin.demo.layout: Unified","M plugin.demo.moved: After"],
      "aria": ["Unified: L","Stale: none","Before: none","After: M"],
      "handled": true,
      "did": ["demo.layout ran for the first view's layout"]
    },
    {
      "step": "M runs on the control it was retargeted to before the facade loaded",
      "keys": ["L plugin.demo.layout: Unified","M plugin.demo.moved: After"],
      "aria": ["Unified: L","Stale: none","Before: none","After: M"],
      "handled": true,
      "did": ["demo.moved ran for Moved"]
    },
    {
      "step": "Q, detached before the facade loaded, was never bound",
      "keys": ["L plugin.demo.layout: Unified","M plugin.demo.moved: After"],
      "aria": ["Unified: L","Stale: none","Before: none","After: M"],
      "handled": false
    },
    {
      "step": "revealed: each live plugin key badges its control, and none is on the strip",
      "keys": ["L plugin.demo.layout: Unified","M plugin.demo.moved: After"],
      "aria": ["Unified: L","Stale: none","Before: none","After: M"],
      "strip": ["Help"],
      "badges": ["L on Unified","M on After"]
    },
    {
      "step": "Help, open: the plugin keys are listed though Help made their controls inert",
      "keys": ["L plugin.demo.layout: not live","M plugin.demo.moved: not live"],
      "aria": ["Unified: L","Stale: none","Before: none","After: M"],
      "controlInert": true,
      "help": [
        ["Anywhere","? Help"],
        ["Controls","L Unified","M Moved"],
        ["Help","? or Esc Close Help"]
      ]
    },
    {
      "step": "T and N are the shell's: refused, with one warning for each command id",
      "keys": ["L plugin.demo.layout: Unified","M plugin.demo.moved: After"],
      "aria": ["Unified: L","Stale: none","Before: none","After: M","Find: none","Next: none"],
      "handledT": false,
      "handledN": false,
      "warned": ["shortcuts.attach: demo.find cannot have T, which the shell reserves; its control has no key","shortcuts.attach: demo.next cannot have N, which the shell reserves; its control has no key"]
    },
    {
      "step": "every letter tried: the facade refuses exactly the reserved ones",
      "keys": ["L plugin.demo.layout: Unified","M plugin.demo.moved: After"],
      "aria": ["Unified: L","Stale: none","Before: none","After: M","Find: none","Next: none"],
      "reservedKeys": ["0: every kind","1: every kind","2: every kind","3: every kind","4: every kind","5: every kind","6: every kind","7: every kind","8: every kind","9: every kind","a: every kind","j: every kind","k: every kind","n: pull-request","p: pull-request","t: every kind","u: every kind","w: every kind","x: every kind","y: every kind"],
      "refused": ["a","j","k","n","p","t","u","w","x","y"]
    },
    {
      "step": "two plugins on O, both shown: the earlier runs and badges, the later is warned",
      "keys": ["L plugin.demo.layout: Unified","M plugin.demo.moved: After","O plugin.alpha.open: Alpha"],
      "aria": ["Unified: L","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: O","Beta: O"],
      "handled": true,
      "badges": ["L on Unified","M on After","O on Alpha"],
      "did": ["alpha.open ran for Open alpha"],
      "warned": ["shortcuts.attach: beta.open loses O to alpha.open, attached earlier; only the winner runs"]
    },
    {
      "step": "the earlier's control hidden: the later's key runs",
      "keys": ["L plugin.demo.layout: Unified","M plugin.demo.moved: After","O plugin.alpha.open: Beta"],
      "aria": ["Unified: L","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: O","Beta: O"],
      "handled": true,
      "did": ["beta.open ran for Open beta"]
    },
    {
      "step": "the earlier lets go: O is registered again with the later's copy",
      "keys": ["L plugin.demo.layout: Unified","M plugin.demo.moved: After","O plugin.beta.open: Beta"],
      "aria": ["Unified: L","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: none","Beta: O"],
      "help": ["Unified","Moved","Open beta"]
    },
    {
      "step": "a shell tab holds L beside the plugin's: the shell's runs and alone badges",
      "keys": ["L plugin.demo.layout: not live","M plugin.demo.moved: After","O plugin.beta.open: Beta"],
      "aria": ["Unified: L","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: none","Beta: O","Log: L"],
      "handled": true,
      "badges": ["M on After","O on Beta","L on Log"],
      "did": ["the shell selected the Log tab"],
      "warned": ["shortcuts.attach: demo.layout loses L to a shell key shown beside it; only the winner runs"]
    },
    {
      "step": "the shell's tab gone: L reaches the plugin again",
      "keys": ["L plugin.demo.layout: Unified","M plugin.demo.moved: After","O plugin.beta.open: Beta"],
      "aria": ["Unified: L","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: none","Beta: O","Log: none"],
      "handled": true,
      "did": ["demo.layout ran for the first view's layout"]
    },
    {
      "step": "a second mount of demo.layout: one command, two targets, the first runs",
      "keys": ["L plugin.demo.layout: Unified","M plugin.demo.moved: After","O plugin.beta.open: Beta"],
      "aria": ["Unified: L","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: none","Beta: O","Log: none","Unified (second view): L"],
      "handled": true,
      "did": ["demo.layout ran for the first view's layout"]
    },
    {
      "step": "the first view hidden: the second's runs",
      "keys": ["L plugin.demo.layout: Unified (second view)","M plugin.demo.moved: not live","O plugin.beta.open: not live"],
      "aria": ["Unified: L","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: none","Beta: O","Log: none","Unified (second view): L"],
      "handled": true,
      "did": ["demo.layout ran for the second view's layout"]
    },
    {
      "step": "the control rebuilt its markup and retargeted: the key moves with it",
      "keys": ["L plugin.demo.layout: Split","M plugin.demo.moved: After","O plugin.beta.open: Beta"],
      "aria": ["Unified: none","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: none","Beta: O","Log: none","Unified (second view): none","Split: L"],
      "handled": true,
      "did": ["demo.layout ran for the first view's layout"]
    },
    {
      "step": "the view taken out of the page: the attachment stays, and does nothing",
      "keys": ["L plugin.demo.layout: not live","M plugin.demo.moved: not live","O plugin.beta.open: not live"],
      "aria": ["Unified: none","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: none","Beta: O","Log: none","Unified (second view): none","Split: L"],
      "handled": false
    },
    {
      "step": "put back while revealed, and retargeted to the same control: badged at once",
      "keys": ["L plugin.demo.layout: Split","M plugin.demo.moved: After","O plugin.beta.open: Beta"],
      "aria": ["Unified: none","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: none","Beta: O","Log: none","Unified (second view): none","Split: L"],
      "badgesBeforeRetarget": 0,
      "badges": ["L on Split","M on After","O on Beta"]
    },
    {
      "step": "the key returns with it",
      "keys": ["L plugin.demo.layout: Split","M plugin.demo.moved: After","O plugin.beta.open: Beta"],
      "aria": ["Unified: none","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: none","Beta: O","Log: none","Unified (second view): none","Split: L"],
      "handled": true,
      "did": ["demo.layout ran for the first view's layout"]
    },
    {
      "step": "staged in the shell's inert stage: not live",
      "keys": ["L plugin.demo.layout: not live","M plugin.demo.moved: not live","O plugin.beta.open: not live"],
      "aria": ["Unified: none","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: none","Beta: O","Log: none","Unified (second view): none","Split: L"],
      "handled": false
    },
    {
      "step": "committed out of the stage: live again",
      "keys": ["L plugin.demo.layout: Split","M plugin.demo.moved: After","O plugin.beta.open: Beta"],
      "aria": ["Unified: none","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: none","Beta: O","Log: none","Unified (second view): none","Split: L"],
      "handled": true,
      "did": ["demo.layout ran for the first view's layout"]
    },
    {
      "step": "its signal aborted, then detached twice: the key is gone, and nothing threw",
      "keys": ["L plugin.demo.layout: Split","M plugin.demo.moved: After","O plugin.beta.open: Beta"],
      "aria": ["Unified: none","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: none","Beta: O","Log: none","Unified (second view): none","Split: L","Close: none"],
      "ariaWhileAttached": "C",
      "handled": false,
      "lateAria": null
    },
    {
      "step": "malformed input throws, prefixed shortcuts.attach:",
      "keys": ["L plugin.demo.layout: Split","M plugin.demo.moved: After","O plugin.beta.open: Beta"],
      "aria": ["Unified: none","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: none","Beta: O","Log: none","Unified (second view): none","Split: L","Close: none"],
      "thrown": ["shortcuts.attach: the element needs an HTMLElement","shortcuts.attach: demo.digit: key must be one letter a-z, not 1","shortcuts.attach: demo.long: key must be one letter a-z, not gg","shortcuts.attach: demo.group: group must be \"view-tabs\" or \"controls\", not tabs","shortcuts.attach: demo.inert: activate must be a function","shortcuts.attach: id must be a dotted name such as \"diff.layout\", not undotted","shortcuts.attach: bindings is not an option; the facade decides it","shortcuts.attach: demo.layout is attached already with another key, group, or copy","shortcuts.attach: retarget needs an HTMLElement"]
    },
    {
      "step": "pagehide: the facade lets go, then the registry is disposed",
      "keys": [],
      "aria": ["Unified: none","Stale: none","Before: none","After: none","Find: none","Next: none","Alpha: none","Beta: none","Log: none","Unified (second view): none","Split: none","Close: none"],
      "handled": false
    },
    {
      "step": "pageshow: a new registry, and every attachment replayed onto it",
      "keys": ["L plugin.demo.layout: Split","M plugin.demo.moved: After","O plugin.beta.open: Beta"],
      "aria": ["Unified: none","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: none","Beta: O","Log: none","Unified (second view): none","Split: L","Close: none"],
      "handled": true,
      "did": ["demo.layout ran for the first view's layout"]
    },
    {
      "step": "a view whose dispose forgot its key: view composition releases it",
      "keys": ["L plugin.demo.layout: Split","M plugin.demo.moved: After","O plugin.beta.open: Beta"],
      "aria": ["Unified: none","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: none","Beta: O","Log: none","Unified (second view): none","Split: L","Close: none","Leaky: none"],
      "ariaWhileMounted": "V",
      "handled": false
    },
    {
      "step": "a view whose dispose removed its own root and forgot its key: released",
      "keys": ["L plugin.demo.layout: Split","M plugin.demo.moved: After","O plugin.beta.open: Beta"],
      "aria": ["Unified: none","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: none","Beta: O","Log: none","Unified (second view): none","Split: L","Close: none","Leaky: none","Rooted: none"],
      "ariaWhileMounted": "R"
    },
    {
      "step": "a render that finished after its stage was cancelled: released",
      "keys": ["L plugin.demo.layout: Split","M plugin.demo.moved: After","O plugin.beta.open: Beta"],
      "aria": ["Unified: none","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: none","Beta: O","Log: none","Unified (second view): none","Split: L","Close: none","Leaky: none","Rooted: none","Slow: none"]
    },
    {
      "step": "a render that attached a key and then failed: released",
      "keys": ["L plugin.demo.layout: Split","M plugin.demo.moved: After","O plugin.beta.open: Beta"],
      "aria": ["Unified: none","Stale: none","Before: none","After: M","Find: none","Next: none","Alpha: none","Beta: O","Log: none","Unified (second view): none","Split: L","Close: none","Leaky: none","Rooted: none","Slow: none","Failing: none"]
    },
    {
      "step": "disposed while queued, before the facade loaded: never bound",
      "keys": [],
      "aria": ["Early: none"],
      "handled": false
    }
  ]
}
? 0
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
