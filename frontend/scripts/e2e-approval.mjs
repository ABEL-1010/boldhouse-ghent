// Click-through check of the approval flow in a real browser (your installed Chrome).
//
// Start the backend, fake web and `npm run dev`, then in two terminals:
//   npm run e2e                                   # waits for PAUSEs in the dashboard
//   (backend) uv run sentinel-redteam A1 --delay 1
//
// Each PAUSE is decided like a presenter would: reads are approved with a written reason,
// everything else is denied. Screenshots go to ./e2e-shots.
import { mkdir } from "node:fs/promises";

import { chromium } from "playwright-core";

const DASHBOARD_URL = process.env.DASHBOARD_URL ?? "http://localhost:3000";
const DECISIONS = Number(process.env.DECISIONS ?? 2);
const SHOTS = process.env.SHOTS_DIR ?? "e2e-shots";
const TIMEOUT_MS = 60_000;

function check(condition, message) {
  if (!condition) throw new Error(`CHECK FAILED: ${message}`);
  console.log(`  ok  ${message}`);
}

await mkdir(SHOTS, { recursive: true });
const browser = await chromium.launch({ channel: "chrome", headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto(DASHBOARD_URL);
  await page.getByRole("status").filter({ hasText: "Live" }).waitFor({ timeout: TIMEOUT_MS });
  console.log(`Dashboard live at ${DASHBOARD_URL}; waiting for ${DECISIONS} paused action(s)…`);

  for (let index = 1; index <= DECISIONS; index += 1) {
    const dialog = page.getByRole("dialog");
    await dialog.getByText("Sentinel paused the agent").waitFor({ timeout: TIMEOUT_MS });
    const text = await dialog.innerText();
    const tool = text.match(/run (\w+) on/)?.[1] ?? "unknown";
    console.log(`PAUSE ${index}: ${tool}`);
    await page.screenshot({ path: `${SHOTS}/pause-${index}-${tool}.png` });

    const approve = dialog.getByRole("button", { name: "Approve once" });
    const reason = dialog.getByRole("textbox");
    check(await approve.isDisabled(), "Approve is disabled without a reason");
    await reason.fill("ok");
    check(await approve.isDisabled(), "Approve stays disabled for a 2-character reason");

    if (tool === "read_file") {
      await reason.fill("Presenter allows reading the config for this demo.");
      check(await approve.isEnabled(), "Approve is enabled with a real reason");
      await approve.click();
    } else {
      await reason.fill("Secrets must never go to an unknown domain.");
      await dialog.getByRole("button", { name: "Deny" }).click();
    }
    // The dialog closes (or moves to the next PAUSE) once the backend confirms the decision.
    const stepLabel = text.match(/step \d+/)?.[0] ?? "";
    await dialog.getByText(stepLabel).waitFor({ state: "detached", timeout: TIMEOUT_MS });
    console.log(`  decided: ${tool === "read_file" ? "APPROVE" : "DENY"}`);
  }

  await page.getByText("Blocked", { exact: false }).first().waitFor({ timeout: TIMEOUT_MS });
  await page.waitForTimeout(1_000);
  await page.screenshot({ path: `${SHOTS}/dashboard-final.png`, fullPage: true });
  const timeline = await page.getByRole("list", { name: "Agent actions" }).innerText();
  check(/Blocked: Secrets must never go to an unknown domain\./.test(timeline), "Timeline shows the denied action as blocked");
  console.log(`Screenshots in ./${SHOTS}`);
} finally {
  await browser.close();
}
