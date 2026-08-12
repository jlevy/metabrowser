// Metabrowser — shared icon registry.
//
// Single source of truth for every SVG icon in the SPA: file tree,
// viz kind icons, log-event chevrons, tally-tree toggles, banners.
// Loaded before app.js and viz.js so both can pull from
// `window.MetabrowserIcons` without duplicating SVG markup.
//
// Icons are Lucide v1.17.0 (ISC; https://lucide.dev) unless a comment
// marks the entry as bespoke. The comment beside each entry is the
// Lucide icon id, so a glyph can be updated or swapped deliberately.
// See https://github.com/jlevy/kpress/blob/v0.3.0/docs/kpress-icons.md for the shared
// icon contract, the add/swap process, and the kpress<->metabrowser glyph map.
//
// Icons are stored as raw SVG with no contextual classes. Callers
// that need a context class (e.g. viz.js wants `viz-kind-icon`) use
// ICON_SVG.withClass(name, cls) to inject it at render time — the
// same raw "doc" shape then serves a .md file in the tree AND a dep
// artifact in the graph without copy-paste.
(() => {
  var SA =
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';

  var ICONS = {
    // Tree / general.
    folder: // Lucide `folder`
      "<svg " +
      SA +
      '><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>',
    file: // Lucide `file`
      "<svg " +
      SA +
      '><path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"/><path d="M14 2v5a1 1 0 0 0 1 1h5"/></svg>',
    fileSymlink: // Lucide `file-symlink`
      "<svg " +
      SA +
      '><path d="M4 11V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.706.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h7"/><path d="M14 2v5a1 1 0 0 0 1 1h5"/><path d="m10 18 3-3-3-3"/></svg>',
    doc: // Lucide `file-text`
      "<svg " +
      SA +
      '><path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"/><path d="M14 2v5a1 1 0 0 0 1 1h5"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/></svg>',
    alignLeft: `<svg ${SA}><path d="M21 5H3"/><path d="M15 12H3"/><path d="M17 19H3"/></svg>`, // Lucide `align-left`
    list: // Lucide `list`
      "<svg " +
      SA +
      '><path d="M3 5h.01"/><path d="M3 12h.01"/><path d="M3 19h.01"/><path d="M8 5h13"/><path d="M8 12h13"/><path d="M8 19h13"/></svg>',
    fileText: // Lucide `file-text`
      "<svg " +
      SA +
      '><path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"/><path d="M14 2v5a1 1 0 0 0 1 1h5"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/></svg>',
    grid: // Lucide `layout-grid`
      "<svg " +
      SA +
      '><rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/></svg>',
    activity: // Lucide `activity`
      "<svg " +
      SA +
      '><path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/></svg>',
    print: // Lucide `printer`
      "<svg " +
      SA +
      '><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><path d="M6 9V3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v6"/><rect x="6" y="14" width="12" height="8" rx="1"/></svg>',
    monitor: // Lucide `monitor`
      "<svg " +
      SA +
      '><rect width="20" height="14" x="2" y="3" rx="2"/><line x1="8" x2="16" y1="21" y2="21"/><line x1="12" x2="12" y1="17" y2="21"/></svg>',
    sun: // Lucide `sun`
      "<svg " +
      SA +
      '><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>',
    moon: // Lucide `moon`
      "<svg " +
      SA +
      '><path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401"/></svg>',
    // Settings gear — the header settings menu trigger.
    gear: // Lucide `settings`
      "<svg " +
      SA +
      '><path d="M9.671 4.136a2.34 2.34 0 0 1 4.659 0 2.34 2.34 0 0 0 3.319 1.915 2.34 2.34 0 0 1 2.33 4.033 2.34 2.34 0 0 0 0 3.831 2.34 2.34 0 0 1-2.33 4.033 2.34 2.34 0 0 0-3.319 1.915 2.34 2.34 0 0 1-4.659 0 2.34 2.34 0 0 0-3.32-1.915 2.34 2.34 0 0 1-2.33-4.033 2.34 2.34 0 0 0 0-3.831A2.34 2.34 0 0 1 6.35 6.051a2.34 2.34 0 0 0 3.319-1.915"/><circle cx="12" cy="12" r="3"/></svg>',
    // Reading-font glyphs (bespoke, not Lucide): a serif vs a sans "A". Use
    // the generic CSS families so the glyph itself shows the difference the
    // option makes.
    serif:
      '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><text x="12" y="18" text-anchor="middle" font-size="20" font-weight="600" font-family="serif">A</text></svg>',
    sans: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><text x="12" y="18" text-anchor="middle" font-size="20" font-weight="600" font-family="sans-serif">A</text></svg>',
    // Viz kind shapes. `dep` shares the `doc` shape deliberately so a
    // .md file in the tree reads as the same visual family as a dep
    // node in the graph.
    step: // Bespoke (not Lucide): rounded square + play glyph for a viz step.
      "<svg " +
      SA +
      '><rect x="2" y="2" width="20" height="20" rx="4" ry="4"/><polygon points="10 8 16 12 10 16 10 8"/></svg>',
    process: // Lucide `box`
      "<svg " +
      SA +
      '><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>',
    dep: // Lucide `file-text` (shares the `doc` shape deliberately)
      "<svg " +
      SA +
      '><path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"/><path d="M14 2v5a1 1 0 0 0 1 1h5"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/></svg>',
    // Controls — chevrons carry their own class so CSS can rotate them.
    chevron: // Lucide `chevron-right`
      '<svg class="log-event-expand" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>',
    toggle: // Lucide `chevron-right`
      '<svg class="toggle-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>',
    // Alert triangle — viz warning banner.
    alert: // Lucide `triangle-alert`
      "<svg " +
      SA +
      '><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>',
  };

  // Return the named icon with an extra `class="..."` injected on the
  // root <svg>. Used by viz.js to wrap shared shapes in its own
  // `viz-kind-icon viz-kind-icon-<kind>` context class.
  ICONS.withClass = (name, cls) => {
    var svg = ICONS[name];
    if (!svg || !cls) {
      return svg || "";
    }
    return svg.replace("<svg ", `<svg class="${cls}" `);
  };

  var g = typeof window !== "undefined" ? window : globalThis;
  if (g) {
    g.MetabrowserIcons = ICONS;
  }
})();
