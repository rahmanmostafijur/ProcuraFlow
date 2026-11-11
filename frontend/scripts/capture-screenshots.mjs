/* global console, process, localStorage */
// Documentation screenshots: 1920x1080 captures of the demo company into docs/screenshots/ (referenced from README.md).
// Needs the demo backend (DEMO_MODE=true after `python -m app.cli.demo_reset`) and the dev server. Usage:
//   node scripts/capture-screenshots.mjs [--base http://127.0.0.1:5180] [--api http://127.0.0.1:8010/api/v1]
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const at = args.indexOf(`--${name}`);
  return at >= 0 ? args[at + 1] : fallback;
};
const OUT = path.resolve(option("out", "../docs/screenshots"));
const BASE = option("base", "http://127.0.0.1:5180");
const API = option("api", "http://127.0.0.1:8010/api/v1");
const VIEWPORT = { width: 1920, height: 1080 };

// file name, route, demo role (null: signed out), theme
const SHOTS = [
  ["landing", "/", null, "light"],
  ["login", "/login", null, "light"],
  ["dashboard", "/dashboard", "admin", "light"],
  ["dashboard-dark", "/dashboard", "admin", "dark"],
  ["requests", "/requests", "admin", "light"],
  ["approvals", "/approvals", "admin", "light"],
  ["purchase-orders", "/purchase-orders", "admin", "light"],
  ["purchase-order", "/purchase-orders/1", "admin", "light"],
  ["invoices", "/invoices", "admin", "light"],
  ["invoice", "/invoices/1", "admin", "light"],
  ["payment-run", "/payment-runs", "admin", "light"],
  ["budgets", "/budgets", "admin", "light"],
  ["suppliers", "/suppliers", "admin", "light"],
  ["inventory", "/inventory", "admin", "light"],
  ["reports", "/reports", "admin", "light"],
  ["supplier-portal", "/portal", "supplier", "light"],
  ["settings", "/settings", "admin", "light"],
];

const browser = await chromium.launch();
const probe = await browser.newPage();
await probe.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
const title = await probe.title();
await probe.close();
if (!/procuraflow/i.test(title)) {
  await browser.close();
  throw new Error(`${BASE} serves "${title}", not ProcuraFlow; check the port`);
}

fs.mkdirSync(OUT, { recursive: true });
for (const [name, route, role, theme] of SHOTS) {
  const context = await browser.newContext({ viewport: VIEWPORT, colorScheme: theme, deviceScaleFactor: 1 });
  await context.addInitScript(
    ([mode]) => {
      localStorage.setItem("pf-theme", mode);
      localStorage.setItem("procuraflow_has_session", "1");
    },
    [theme],
  );
  if (role) {
    const response = await context.request.post(`${API}/auth/demo-login`, { data: { role } });
    if (!response.ok()) throw new Error(`demo-login ${role} failed: ${response.status()}`);
  }
  const page = await context.newPage();
  await page.goto(`${BASE}${route}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await page.screenshot({ path: path.join(OUT, `${name}.png`) });
  await context.close();
  console.log(`${name}.png`);
}
await browser.close();
