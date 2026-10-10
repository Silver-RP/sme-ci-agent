// Screenshots of every main state at 1920x1080 (brief DoD: one per state in the PR), from the replay so no
// backend is needed. Usage: yarn build && yarn start -p 3100, then
//   BASE=http://localhost:3100 yarn shots            (writes to dashboard/screenshots/, gitignored)
// Set THEME=dark for the dark theme. Chromium: PLAYWRIGHT_BROWSERS_PATH or a local `npx playwright install chromium`.

import fs from "node:fs";
import path from "node:path";
import { chromium } from "@playwright/test";

const BASE = process.env.BASE ?? "http://localhost:3100";
const OUT = path.resolve(import.meta.dirname, "../screenshots");
const THEME = process.env.THEME === "dark" ? "dark" : "light";
fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
await page.addInitScript((theme) => localStorage.setItem("sme.theme", theme), THEME);

async function shot(name) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(400);
  const file = path.join(OUT, `${THEME}-${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  console.log("saved", file);
}

async function replay(file, speedUp = true) {
  await page.goto(`${BASE}/?source=fixture&file=${file}`);
  if (speedUp) await page.getByTestId("replay-speed").click();
}

const approve = async (label = "Duyệt") => {
  await page.getByLabel("Người duyệt").selectOption("alice");
  await page.getByRole("button", { name: label, exact: true }).click();
};

// start screen (live mode, no backend call until the click)
await page.goto(`${BASE}/?source=live`);
await shot("01-start");

// happy path: thinking -> question -> proposal -> outcome
await replay("run-happy");
await page.waitForTimeout(500);
await shot("02-thinking");
await page.getByTestId("question-stage").waitFor();
await shot("03-question");
await page.getByLabel("Câu trả lời của bạn").fill("Ca đêm có người thay ca, lô nguyên liệu không đổi.");
await page.getByTestId("answer-submit").click();
await page.getByTestId("decision-panel").waitFor({ timeout: 20000 });
await shot("04-proposal");
await approve();
await page.getByTestId("outcome-stage").waitFor({ timeout: 20000 });
await page.getByTestId("event-log").getByRole("button").first().click();
await shot("05-completed");

// rollback
await replay("run-rollback");
await page.getByTestId("decision-panel").waitFor({ timeout: 20000 });
await approve();
await page.locator('[data-kind="rollback"]').waitFor({ timeout: 20000 });
await shot("06-rollback");

// halt after a declined rollback
await replay("run-rollback-declined");
await page.getByTestId("decision-panel").waitFor({ timeout: 20000 });
await approve();
await page.locator('[data-kind="rollback"]').waitFor({ timeout: 20000 });
await approve("Giữ SOP hiện tại");
await page.locator('[data-kind="halt"]').waitFor({ timeout: 20000 });
await shot("07-halt");

// insufficient evidence
await replay("run-insufficient-evidence");
await page.getByTestId("decision-panel").waitFor({ timeout: 20000 });
await approve();
await page.getByTestId("question-stage").waitFor({ timeout: 20000 });
await shot("08-insufficient");

// error + retry
await replay("run-error-retry");
await page.getByTestId("run-error").waitFor({ timeout: 20000 });
await shot("09-error");

// no anomaly
await replay("run-no-anomaly");
await page.getByTestId("outcome-stage").waitFor({ timeout: 20000 });
await shot("10-no-anomaly");

for (const [name, url] of [
  ["11-runs", "/runs"],
  ["12-overview", "/overview"],
  ["13-kaizen", "/kaizen"],
  ["14-audit", "/audit"],
]) {
  await page.goto(`${BASE}${url}`);
  await shot(name);
}

// presentation mode on the proposal
await replay("run-happy");
await page.getByTestId("question-stage").waitFor({ timeout: 20000 });
await page.keyboard.press("f");
await page.getByLabel("Câu trả lời của bạn").fill("Không có thêm thông tin.");
await page.getByTestId("answer-submit").click();
await page.getByTestId("decision-panel").waitFor({ timeout: 20000 });
await shot("15-present-proposal");
await page.keyboard.press("f");

await browser.close();
