// WP67 §4: the owner's workflow through the real browser — project, inputs, run, checkpoint, accept, model, artefacts.
import { chromium } from "playwright";
import { readFileSync } from "node:fs";

const [base, reqPath, schemaPath, shotDir] = process.argv.slice(2);
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
page.on("pageerror", (e) => console.log("PAGEERROR", e.message));
const t0 = Date.now();
const log = (...a) => console.log(`[${((Date.now() - t0) / 1000).toFixed(1)}s]`, ...a);

await page.goto(base);
const name = process.env.WALK_PROJECT ?? `Health insurance (browser ${new Date().toISOString().slice(11, 19)})`;
await page.getByLabel("new project name").fill(name);
await page.getByRole("button", { name: "+" }).click();
await page.getByRole("heading", { name: "Project" }).waitFor();
log("project created", page.url());

await page.getByLabel("attach requirements").setInputFiles(reqPath);
await page.getByText(reqPath.split("/").pop()).first().waitFor();
if (schemaPath) {
  await page.getByLabel("attach schema").setInputFiles(schemaPath);
  await page.getByText(schemaPath.split("/").pop()).first().waitFor();
}
log("inputs attached");
await page.screenshot({ path: `${shotDir}/1-project.png` });

await page.getByRole("button", { name: "Run the generator" }).click();
await page.getByRole("tab", { name: "Run" }).waitFor();
log("run started", page.url());
await page.waitForFunction(() => document.body.innerText.includes("Open the checkpoint"), null, { timeout: 15 * 60 * 1000 });
const strip = await page.$$eval("[aria-label='pipeline status (derived from the trace)'] [data-state]", (els) => els.map((e) => e.dataset.state));
log("paused; strip:", strip.join(","));
await page.screenshot({ path: `${shotDir}/2-run-paused.png` });

await page.getByRole("button", { name: "Open the checkpoint" }).click();
await page.getByText(/decisions$/).first().waitFor();
const header = await page.locator("header:has-text('Checkpoint')").innerText();
log("checkpoint:", header.replace(/\n/g, " | "));
for (const input of await page.getByLabel(/^owner for /).all()) await input.fill("Jane Doe <jane@example.com>");
for (const input of await page.getByLabel(/^resolution for /).all()) await input.fill("NEW");
await page.screenshot({ path: `${shotDir}/3-review.png` });
await page.getByRole("button", { name: "Accept and continue" }).click();
await page.waitForFunction(() => /\bfinished\b/.test(document.querySelector("footer")?.innerText ?? ""), null, { timeout: 15 * 60 * 1000 });
log("finished");
const cli = await page.locator("pre").first().innerText();
log("cli equivalents:\n  " + cli.replace(/\n/g, "\n  "));
await page.screenshot({ path: `${shotDir}/4-run-finished.png` });

await page.getByRole("tab", { name: "Model" }).click();
await page.waitForFunction(() => document.querySelectorAll(".mermaid-host svg").length >= 1, null, { timeout: 60_000 });
const inventory = await page.locator("header:has-text('Inventory')").innerText();
log("model:", inventory.replace(/\n/g, " | "), "| svgs:", await page.locator(".mermaid-host svg").count());
await page.screenshot({ path: `${shotDir}/5-model.png`, fullPage: true });

await page.getByRole("tab", { name: "Artefacts" }).click();
await page.getByText("report.html").waitFor();
const files = await page.locator("section:has-text('Output directory') button").count();
await page.getByText("review-queue.md").click();
await page.locator("pre").waitFor();
log("artefacts:", files, "files; review-queue.md opened");
await page.screenshot({ path: `${shotDir}/6-artefacts.png` });

await page.getByRole("tab", { name: "Log" }).click();
const lines = await page.locator("[aria-label='event stream'] li").count();
log("log lines:", lines);
await browser.close();
console.log("WALK OK");
