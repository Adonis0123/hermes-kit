// Capture Live Copy with ego-browser (the user's Ego Lite, so its logins apply).
//   ego-browser nodejs < ego_capture.js
// Args come from $WORK/ego-args.json (ego's node process gets no argv/env):
//   {"space": 12 | null, "url": "https://..." | null, "out": "/abs/live.txt", "page": "p1"}
// - space null → new TaskSpace; reuse the printed spaceId on every later call.
// - url set → navigate there and dismiss promo popups; url null → capture the
//   page as it is now (after the agent opened a dialog/menu/tab itself).
// Writes the visible text of the open dialog (or the whole page) plus hover-only
// copy to `out`, one line each, and prints a JSON summary.
const fs = await import("node:fs/promises");
const os = await import("node:os");
const path = await import("node:path");
const skill = path.join(os.homedir(), ".hermes/skills/productivity/figma-copy-proofread");
const work = path.join(process.env.HERMES_HOME || path.join(os.homedir(), ".hermes"), "cache/figma-copy-proofread");
const args = JSON.parse(await fs.readFile(path.join(work, "ego-args.json"), "utf8"));

const task = args.space ? await taskSpace(args.space) : await taskSpace("figma copy proofread");
const page = task.page(args.page || "p1");

if (args.url) {
  await page.goto(args.url);
  await page.waitForLoadState();
  await page.waitForTimeout(3000);
  // Promo popups only: a dialog whose text looks like marketing, closed by its own Close / Got it.
  await page.evaluate(() => {
    const promo = /Try Now|See previous updates|Unlock|Subscriber Perk|now in one studio/i;
    for (const d of document.querySelectorAll('[role=dialog], [class*=toast], [class*=guide]')) {
      if (!promo.test(d.innerText || "")) continue;
      const btn = [...d.querySelectorAll("button")].find((b) => /^(close|got it)$/i.test((b.getAttribute("aria-label") || b.innerText || "").trim()));
      if (btn) btn.click();
    }
    const gotIt = [...document.querySelectorAll("button")].find((b) => (b.innerText || "").trim() === "Got it");
    if (gotIt) gotIt.click();
  });
  await page.waitForTimeout(800);
}

const captured = await page.evaluate(() => {
  const visible = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const skip = /Caption|Beginning of dialog/;
  const layers = [...document.querySelectorAll('[role=dialog], [role=menu], [role=listbox]')]
    .filter((d) => visible(d) && (d.innerText || "").trim() && !skip.test(d.innerText));
  const scope = layers.length ? layers : [document.body];
  return {
    scope: layers.length ? layers.map((d) => d.getAttribute("role")).join("+") : "page",
    lines: scope.flatMap((d) => d.innerText.split("\n")).map((l) => l.trim()).filter(Boolean),
    url: location.href,
    signedIn: !/(^|\n)Login(\n|$)/.test(document.body.innerText),
  };
});

let hover = [];
const harvest = await fs.readFile(path.join(skill, "scripts/harvest_hover_text.js"), "utf8");
for (let start = 0; ; start += 12) {
  const r = await page.evaluate(harvest.replace("const START = 0;", `const START = ${start};`));
  hover = hover.concat(r.found);
  if (!r.more) break;
}

const lines = [...captured.lines, ...hover.map((h) => h.text)];
await fs.writeFile(args.out, lines.join("\n") + "\n", "utf8");
console.log(JSON.stringify({
  spaceId: task.spaceId, page: page.label, url: captured.url, scope: captured.scope,
  signedIn: captured.signedIn, lines: captured.lines.length, hover, out: args.out,
}));
