// WP69 §4: an interrupted run (a server that died mid-run, reconciled at the next start) is
// continued from the Run tab, reaches the checkpoint, and the resume command is recorded.
import { chromium } from "playwright";

const [base, runUrl, shotDir] = process.argv.slice(2);
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
page.on("pageerror", (e) => console.log("PAGEERROR", e.message));
await page.goto(base + runUrl);
await page.getByRole("button", { name: "Continue the run" }).waitFor({ timeout: 30_000 });
const status = await page.locator("footer").innerText();
console.log("before:", status.split("\n")[0]);
await page.screenshot({ path: `${shotDir}/7-interrupted.png` });
await page.getByRole("button", { name: "Continue the run" }).click();
await page.getByRole("button", { name: "Open the checkpoint" }).waitFor({ timeout: 120_000 });
const cli = await page.locator("main pre").first().innerText();
console.log("after continue: paused; cli equivalents:\n  " + cli.replace(/\n/g, "\n  "));
if (!/resume --out \S+\n?$/m.test(cli.split("\n").slice(-1)[0] + "\n") && !cli.includes("resume --out")) throw new Error("no resume equivalent recorded");
await page.screenshot({ path: `${shotDir}/8-continued.png` });
await browser.close();
console.log("INTERRUPTED WALK OK");
