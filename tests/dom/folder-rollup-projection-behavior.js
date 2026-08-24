const fs = require("node:fs");
const path = require("node:path");

async function main() {
  const repoRoot = path.resolve(process.argv[2]);
  const source = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/rollup-projection.js"),
    "utf8",
  );
  const module = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
  const pool = module.createFolderRollupProjectionPool();
  const totals = pool.acquire("src");
  const breakdown = pool.acquire("src");
  const seen = [];
  totals.subscribe(() => {
    throw new Error("isolated listener failure");
  });
  const unsubscribe = totals.subscribe((envelope) => seen.push(envelope));
  const first = { path: "src", revision: 1 };
  breakdown.publish(first);
  if (seen.length !== 1 || seen[0] !== first) {
    throw new Error(`one listener failure interrupted sibling projection: ${JSON.stringify(seen)}`);
  }
  const late = pool.acquire("src");
  let replayed = null;
  const unsubscribeLate = late.subscribe((envelope) => {
    replayed = envelope;
  });
  if (replayed !== first) {
    throw new Error("late consumers must receive the current projection");
  }
  const releasedSubscriber = pool.acquire("src");
  let deliveriesAfterRelease = 0;
  releasedSubscriber.subscribe(() => {
    deliveriesAfterRelease += 1;
  });
  deliveriesAfterRelease = 0;
  releasedSubscriber.release();
  unsubscribe();
  totals.release();
  const second = { path: "src", revision: 2 };
  breakdown.publish(second);
  if (replayed !== second) {
    throw new Error("one release must not dispose a shared projection session");
  }
  if (deliveriesAfterRelease !== 0) {
    throw new Error("releasing a projection lease must remove its subscriptions");
  }
  unsubscribeLate();
  late.release();
  breakdown.release();

  const fresh = pool.acquire("src");
  let staleReplay = false;
  const unsubscribeFresh = fresh.subscribe(() => {
    staleReplay = true;
  });
  if (staleReplay) {
    throw new Error("the final release must discard the path projection");
  }
  unsubscribeFresh();
  fresh.release();
  console.log(JSON.stringify({ ok: true }));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
