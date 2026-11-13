// exp-065 (H92) and exp-080 (H106): readings the transition compare does not name, derived
// from the full transition rows of one series. Writes one JSON line per valid run and
// pull request transition, and one per run with the per-run figures the rounds decide on.
//
// node derive-h92-h106.mjs RUNS.jsonl OUT.jsonl
import fs from "node:fs";

const [input, output] = process.argv.slice(2);
const rows = fs
  .readFileSync(input, "utf8")
  .trim()
  .split("\n")
  .map((line) => JSON.parse(line));
const valid = rows.filter((row) => row.valid);

// The pull request clicks of the pulls journey, each of which selects a row and opens it.
const CLICKS = [
  "pulls.list_to_pr.cold",
  "pulls.pr_to_pr.cold",
  "pulls.pr_to_pr.revisit",
  "pulls.pr_to_pr.hover_click",
  "pulls.pr_changes_to_pr",
];
// Every paint of Changes in the pulls journey: a pull request's first visit to the tab, and
// the return to it from Checks or Conversation, which mounts the comparison again.
const CHANGES = [
  "pulls.tab.changes_first",
  "pulls.tab.changes_revisit",
  "pulls.tab.changes_first_2",
  "pulls.tab.changes_revisit_2",
];
// A source node inside the pull request page's body: its cards, sections, commit rows,
// the diff and its files, and rendered Markdown (the pilot's rule, unchanged).
const BODY =
  /github-pull-body|github-pull-card|github-pull-section|github-pull-commit|diff-|github-pull-diff|kpress/;

const round4 = (v) => Math.round(v * 1e4) / 1e4;
const out = [];
for (const row of valid) {
  const perRun = {
    kind: "run",
    condition: row.condition,
    run: row.run,
    pair: row.pair,
    subjectDuplicatesOnClicks: 0,
    clicksMeasured: 0,
    changesBodyShiftAfterReady: 0,
    changesMeasured: 0,
    conversationTransitions: 0,
    plainFirstTransitions: 0,
    plainFirst: [],
    conversationBodyShiftAfterReady: 0,
  };
  for (const journey of row.journeys ?? []) {
    for (const t of journey.transitions ?? []) {
      const prTransition = t.id.startsWith("pulls.") || /_to_pulls$/.test(t.id);
      if (!prTransition) {
        continue;
      }
      const ready = t.paintedReadyMs ?? 0;
      const entries = t.shifts?.entries ?? [];
      const inBody = (e) => e.src.some((s) => BODY.test(s.n));
      const after = entries.filter((e) => e.t > ready && inBody(e));
      const shown = t.milestones?.prDescriptionShown ?? null;
      const final = t.milestones?.prDescriptionFinal ?? null;
      const conversation = !!t.milestones && "prDescriptionShown" in t.milestones;
      const gap = shown !== null && final !== null ? Math.round((final - shown) * 10) / 10 : null;
      const record = {
        kind: "transition",
        condition: row.condition,
        run: row.run,
        pair: row.pair,
        id: t.id,
        subject: t.subject,
        paintedReadyMs: t.paintedReadyMs,
        subjectDuplicates: t.requests?.subjectDuplicates ?? null,
        subjectSettlementReads: t.requests?.subjectSettlementReads ?? null,
        prDescriptionShownMs: shown,
        prDescriptionFinalMs: final,
        descriptionFinalGapMs: gap,
        bodyShiftAfterReady: round4(after.reduce((a, e) => a + e.v, 0)),
        bodyShiftAfterReadyNoInput: round4(
          after.filter((e) => !e.input).reduce((a, e) => a + e.v, 0),
        ),
        shiftSumNoInput: t.shifts?.sumNoInput ?? null,
        prBodyMovement: t.regions?.prBody ?? null,
        loadAvg: t.loadAvg ?? null,
      };
      out.push(record);
      if (CLICKS.includes(t.id) && record.subjectDuplicates !== null) {
        perRun.subjectDuplicatesOnClicks += record.subjectDuplicates;
        perRun.clicksMeasured += 1;
      }
      if (CHANGES.includes(t.id)) {
        perRun.changesBodyShiftAfterReady = round4(
          perRun.changesBodyShiftAfterReady + record.bodyShiftAfterReady,
        );
        perRun.changesMeasured += 1;
      }
      if (conversation) {
        perRun.conversationTransitions += 1;
        perRun.conversationBodyShiftAfterReady = round4(
          perRun.conversationBodyShiftAfterReady + record.bodyShiftAfterReady,
        );
        if (gap !== null && gap > 0) {
          perRun.plainFirstTransitions += 1;
          perRun.plainFirst.push(`${t.id} +${gap}`);
        }
      }
    }
  }
  out.push(perRun);
}
fs.writeFileSync(output, `${out.map((r) => JSON.stringify(r)).join("\n")}\n`);

// The per-run figures and the deciding transitions, by condition, with pair ratios.
const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};
const show = (label, pick) => {
  const by = {};
  for (const r of out) {
    const v = pick(r);
    if (v !== undefined && v !== null) {
      by[r.condition] ??= [];
      by[r.condition].push({ v, pair: r.pair });
    }
  }
  const c = (by.control ?? []).map((x) => x.v);
  const k = (by.candidate ?? []).map((x) => x.v);
  const fmt = (xs) =>
    xs.length ? `${median(xs)} [${Math.min(...xs)}, ${Math.max(...xs)}] n${xs.length}` : "-";
  const ratios = (by.candidate ?? [])
    .map((x) => {
      const partner = (by.control ?? []).find((y) => y.pair === x.pair);
      return partner && partner.v !== 0
        ? Math.round((x.v / partner.v) * 100) / 100
        : partner
          ? `${x.v}/0`
          : "?";
    })
    .join(" ");
  const overlap =
    c.length && k.length
      ? !(Math.max(...k) < Math.min(...c) || Math.min(...k) > Math.max(...c))
      : null;
  console.log(
    `${label.padEnd(64)} control ${fmt(c).padEnd(26)} candidate ${fmt(k).padEnd(26)} overlap ${overlap} pairs ${ratios}`,
  );
};
console.log(`${out.length} rows from ${valid.length} valid of ${rows.length} runs`);
show("run: subject duplicates on the five clicks", (r) =>
  r.kind === "run" ? r.subjectDuplicatesOnClicks : undefined,
);
show("run: Changes body shift after ready (four paints)", (r) =>
  r.kind === "run" ? r.changesBodyShiftAfterReady : undefined,
);
show("run: Conversation transitions plain first", (r) =>
  r.kind === "run" ? r.plainFirstTransitions : undefined,
);
show("run: Conversation body shift after ready", (r) =>
  r.kind === "run" ? r.conversationBodyShiftAfterReady : undefined,
);
const ids = [...new Set(out.filter((r) => r.kind === "transition").map((r) => r.id))];
for (const id of ids) {
  const pick = (key) => (r) => (r.kind === "transition" && r.id === id ? r[key] : undefined);
  show(`${id} subjectDuplicates`, pick("subjectDuplicates"));
  show(`${id} bodyShiftAfterReady`, pick("bodyShiftAfterReady"));
  show(`${id} descriptionFinalGapMs`, pick("descriptionFinalGapMs"));
}
