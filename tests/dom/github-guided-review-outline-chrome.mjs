// Guided Review's step list in headless Chrome, against a live `metab` server that serves the
// GitHub stand-in with three guides (tests/github_pull_fixture.py): pull request 7's, an
// overview and two steps in no group; 8's rewritten as `mixed`, a group of one step and then
// a step in no group; and 9's as `ten-steps`, ten steps in no group, whose numbers run to two
// digits.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> node tests/dom/github-guided-review-outline-chrome.mjs <base URL>
//
// tests/test_github_guided_review_chrome.py builds that server, owns the profile directory, and
// stops this process's whole group, Chrome included, however the run ends.
//
// What only a browser holds, and the browserless session cannot
// (github-guided-review-mount-behavior.js pins which rows have a number and how many digits
// the list's column outside a group is wide for): where each row's text starts. A row outside
// any group is not indented (mb-420k): the overview's title, which has no number, and a
// step's number start on the edge a group's heading's text starts on, and the titles of
// those steps line up, one digit or two. A group's steps keep their column under its
// heading: each number set to the end of a column 1.5em wide that starts on that edge, and
// their titles in line. Every row is one box, so the current step's marker and the focus
// ring sit on the same edges for a row in a group and one outside. Each is measured in the
// light and the dark scheme, at a desktop width and at a phone's with the navigation pane
// hidden, as the reading column is on a phone. A guide with no group has no heading, so its
// edge is a heading's set in its list for the measurement.
import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
if (!base || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES) {
  throw new Error(
    "usage: CHROME_BIN CHROME_PROFILES github-guided-review-outline-chrome.mjs <base>",
  );
}
// One page load or fake gh fetch; a loaded machine has needed several seconds for one.
const STEP_MS = 30000;
// Text is placed at fractional pixels, and two edges set from the same one round alike.
const NEAR = 0.5;

const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};
const same = (label, got, want) =>
  check(label, JSON.stringify(got) === JSON.stringify(want), `got ${JSON.stringify(got)}`);
const near = (a, b) => Math.abs(a - b) <= NEAR;
/** Whether every value of *values* is within NEAR of the first. */
const aligned = (values) => values.every((value) => near(value, values[0]));

/** The step list as the browser lays it out: where a group heading's text starts, and each
 * row's box, marker, and where its number's digits and its title's text start, in pixels
 * from that edge. In a guide with no group, a heading is set in the list to be measured and
 * taken out again. Each token the rows paint from is resolved on a probe of its own. */
const LIST = `(() => {
  const list = document.querySelector(".github-pull-guide-steps");
  const text = (node) => {
    const range = document.createRange();
    range.selectNodeContents(node);
    return range.getBoundingClientRect();
  };
  let heading = list.querySelector(".github-pull-guide-steps-heading");
  const set = heading === null;
  if (set) {
    const item = document.createElement("li");
    heading = document.createElement("div");
    heading.className = "group-heading github-pull-guide-steps-heading";
    heading.textContent = "Probe";
    item.append(heading);
    list.append(item);
  }
  const edge = text(heading).left;
  if (set) {
    heading.parentElement.remove();
  }
  const resolved = (property, value) => {
    const probe = document.createElement("div");
    probe.style.setProperty(property, value);
    list.append(probe);
    const got = getComputedStyle(probe).getPropertyValue(property);
    probe.remove();
    return got;
  };
  const rows = [...list.querySelectorAll(".github-pull-guide-steps-link")].map((link) => {
    // A number's place: an empty one, as the overview's once was, holds no digits to place.
    const place = link.querySelector(".github-pull-guide-steps-number");
    const number = place?.textContent ? place : null;
    const box = link.getBoundingClientRect();
    const style = getComputedStyle(link);
    const column = number === null ? null : number.getBoundingClientRect();
    return {
      title: link.querySelector(".github-pull-guide-steps-title").textContent,
      grouped: link.closest(".github-pull-guide-steps-members") !== null,
      titleAt: text(link.querySelector(".github-pull-guide-steps-title")).left - edge,
      place: place !== null,
      number:
        number === null
          ? null
          : {
              at: text(number).left - edge,
              end: text(number).right - edge,
              columnAt: column.left - edge,
              columnEnd: column.right - edge,
              columnWidth: column.width,
              em: parseFloat(getComputedStyle(number).fontSize),
            },
      left: box.left,
      right: box.right,
      current: link.getAttribute("aria-current") === "step",
      bar: style.borderInlineStartColor,
      barWidth: style.borderInlineStartWidth,
      focused: document.activeElement === link,
      ring: [style.outlineStyle, style.outlineWidth, style.outlineColor],
    };
  });
  return {
    rows,
    tokens: {
      bar: resolved("border-left-color", "var(--highlight-bar)"),
      ring: resolved("outline-color", "var(--focus-ring-color)"),
      ringWidth: resolved("width", "var(--focus-ring-width)"),
    },
    theme: document.documentElement.getAttribute("data-theme"),
  };
})()`;

/** Check the list as LIST measured it, under *label*. */
function measure(label, { rows, tokens }) {
  const loose = rows.filter((row) => !row.grouped);
  const grouped = rows.filter((row) => row.grouped);
  for (const row of loose) {
    const first = row.number === null ? row.titleAt : row.number.at;
    check(
      `${label}: "${row.title}", outside a group, starts on a group heading's edge`,
      near(first, 0),
      `${first.toFixed(2)} px from it`,
    );
  }
  const overview = rows.find((row) => row.title === "Overview");
  if (overview !== undefined) {
    check(`${label}: the overview has no number, nor a place for one`, !overview.place);
  }
  const numbered = loose.filter((row) => row.number !== null);
  check(
    `${label}: the titles of the steps outside a group line up`,
    aligned(numbered.map((row) => row.titleAt)),
    numbered.map((row) => row.titleAt.toFixed(2)).join(", "),
  );
  for (const row of grouped) {
    const { number } = row;
    check(
      `${label}: "${row.title}", in a group, keeps its column on the heading's edge, 1.5em wide, its number set to the column's end`,
      near(number.columnAt, 0) &&
        near(number.columnWidth, 1.5 * number.em) &&
        near(number.end, number.columnEnd) &&
        number.at > NEAR,
      JSON.stringify(number),
    );
  }
  check(
    `${label}: the titles of a group's steps line up`,
    aligned(grouped.map((row) => row.titleAt)),
    grouped.map((row) => row.titleAt.toFixed(2)).join(", "),
  );
  check(
    `${label}: every row is one box, so its marker and its focus ring share the list's edges`,
    aligned(rows.map((row) => row.left)) && aligned(rows.map((row) => row.right)),
    JSON.stringify(rows.map((row) => [row.left, row.right])),
  );
  const current = rows.filter((row) => row.current);
  check(
    `${label}: the current row alone is marked, in --highlight-bar`,
    current.length === 1 &&
      current[0].bar === tokens.bar &&
      rows.every((row) => row.current || row.bar !== tokens.bar),
    JSON.stringify(rows.map((row) => [row.title, row.current, row.bar])),
  );
  for (const row of rows.filter((each) => each.focused)) {
    same(`${label}: the focused row "${row.title}" draws the focus ring`, row.ring, [
      "solid",
      tokens.ringWidth,
      tokens.ring,
    ]);
  }
}

const chrome = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
});
try {
  const { evaluate } = chrome;
  const waitFor = (expression) => chrome.waitFor(expression, STEP_MS);
  // `\`, which hides the navigation pane and shows it again (static/nav-collapse.js).
  const togglePane = async () => {
    const key = { key: "\\", code: "Backslash", windowsVirtualKeyCode: 220 };
    await chrome.send("Input.dispatchKeyEvent", { type: "keyDown", text: "\\", ...key });
    await chrome.send("Input.dispatchKeyEvent", { type: "keyUp", ...key });
  };
  // The shell follows the system's scheme by setting `data-theme` when the media query
  // changes (static/app.js), so a scheme is in force once the attribute names it.
  const scheme = async (value) => {
    await chrome.send("Emulation.setEmulatedMedia", {
      features: [{ name: "prefers-color-scheme", value }],
    });
    await waitFor(
      `document.documentElement.getAttribute("data-theme") === ${JSON.stringify(value)}`,
    );
  };
  const COLLAPSED = `document.querySelector(".container").hasAttribute("data-nav-collapsed")`;
  /** Each row's marker in the light scheme and in the dark, so the two can differ. */
  const bars = { light: new Set(), dark: new Set() };
  await chrome.send("Page.enable");

  /** Open *route*'s guide and measure its list in each scheme, at both widths. With *focus*,
   * the row titled so is focused from the keyboard first. */
  const each = async (route, name, focus = null) => {
    await chrome.send("Page.navigate", { url: `${base}${route}` });
    await waitFor(`location.pathname === ${JSON.stringify(route)}`);
    await waitFor(
      `document.querySelector(".github-pull-guide-position")?.textContent === "Overview"`,
    );
    await waitFor(`document.fonts.status === "loaded"`);
    // The page's keys, `\` among them, once it has attached them.
    await waitFor(
      `document.querySelector(".github-pull .tab-btn")?.getAttribute("aria-keyshortcuts") !== null`,
    );
    if (focus !== null) {
      // A key first, so a focus from script is the keyboard's and shows its ring.
      const tab = { key: "Tab", code: "Tab", windowsVirtualKeyCode: 9 };
      await chrome.send("Input.dispatchKeyEvent", { type: "keyDown", ...tab });
      await chrome.send("Input.dispatchKeyEvent", { type: "keyUp", ...tab });
      await evaluate(
        `[...document.querySelectorAll(".github-pull-guide-steps-link")].find((link) => link.textContent.includes(${JSON.stringify(focus)})).focus()`,
      );
    }
    const take = async (label, value) => {
      await scheme(value);
      const measured = await evaluate(LIST);
      same(`${label}: the page's scheme`, measured.theme, value);
      for (const row of measured.rows.filter((row) => row.current)) {
        bars[value].add(row.bar);
      }
      measure(label, measured);
      return measured;
    };
    const desktop = await take(`${name}, light, desktop`, "light");
    await take(`${name}, dark, desktop`, "dark");
    await chrome.send("Emulation.setDeviceMetricsOverride", {
      width: 375,
      height: 812,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await waitFor(`window.innerWidth === 375`);
    await togglePane();
    await waitFor(
      `${COLLAPSED} && document.querySelector(".github-pull-guide-outline").getBoundingClientRect().width > 250`,
    );
    await take(`${name}, dark, phone`, "dark");
    await take(`${name}, light, phone`, "light");
    await togglePane();
    await waitFor(`!${COLLAPSED}`);
    await chrome.send("Emulation.clearDeviceMetricsOverride");
    return desktop;
  };

  // 7's guide: an overview and two steps, in no group.
  const flat = await each("/pull/7/guided", "a guide with no group");
  same(
    "7's list",
    flat.rows.map((row) => [row.title, row.grouped]),
    [
      ["Overview", false],
      ["Start with the count", false],
      ["Read the new guide", false],
    ],
  );

  // 8's guide: a group of one step, then a step in no group, which is focused from the keys.
  const mixed = await each("/pull/8/guided", "a group, then a step", "Read the new guide");
  same(
    "8's list",
    mixed.rows.map((row) => [row.title, row.grouped, row.focused]),
    [
      ["Overview", false, false],
      ["Start with the count", true, false],
      ["Read the new guide", false, true],
    ],
  );
  // The step outside a group, chosen, is marked on the same box as the overview was.
  await evaluate(
    `[...document.querySelectorAll(".github-pull-guide-steps-link")].find((link) => link.textContent.includes("Read the new guide")).click()`,
  );
  await waitFor(
    `document.querySelector(".github-pull-guide-position")?.textContent === "Step 2 of 2"`,
  );
  await scheme("light");
  const chosen = await evaluate(LIST);
  measure("a group, then a step, its second step shown", chosen);
  same(
    "the step outside a group is the one marked",
    chosen.rows.filter((row) => row.current).map((row) => row.title),
    ["Read the new guide"],
  );

  // 9's guide: ten steps in no group, numbered 1 to 10.
  const ten = await each("/pull/9/guided", "ten steps");
  same("9's numbers", ten.rows.filter((row) => row.number !== null).length, 10);
  check(
    "the light and the dark scheme mark the current row in their own colors",
    bars.light.size === 1 && bars.dark.size === 1 && [...bars.light][0] !== [...bars.dark][0],
    JSON.stringify({ light: [...bars.light], dark: [...bars.dark] }),
  );
} finally {
  await chrome.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exitCode = 1;
} else {
  process.stdout.write(`guided review outline in Chrome: ${checks} checks passed\n`);
}
