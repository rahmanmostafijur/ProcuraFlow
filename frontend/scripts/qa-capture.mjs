/* global console, process, window, document, localStorage, getComputedStyle */
// Visual QA capture: every page at three viewports in light and dark, with an axe run and an overflow check.
// Needs the demo backend and the dev server running (see HowToSetup.md). Usage:
//   node scripts/qa-capture.mjs [--out ../docs/qa-screens] [--base http://127.0.0.1:5173] [--api http://127.0.0.1:8010/api/v1]
//   add --only <substring> to restrict to matching page paths, --quick for one viewport and theme.
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { chromium } from "playwright";

const require = createRequire(import.meta.url);
const AXE_SOURCE = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const at = args.indexOf(`--${name}`);
  return at >= 0 ? args[at + 1] : fallback;
};
const OUT = path.resolve(option("out", "../docs/qa-screens"));
const BASE = option("base", "http://127.0.0.1:5180");
const API = option("api", "http://127.0.0.1:8010/api/v1");
const ONLY = option("only", "");
const QUICK = args.includes("--quick");

const VIEWPORTS = [
  { name: "1440x900", width: 1440, height: 900 },
  { name: "1024x768", width: 1024, height: 768 },
  { name: "390x844", width: 390, height: 844 },
];
const THEMES = ["light", "dark"];
const MAX_PAGE_HEIGHT = 7000;

const PUBLIC_PAGES = ["/", "/login", "/forgot-password"];
const INTERNAL_PAGES = [
  "/dashboard",
  "/suppliers",
  "/suppliers/1",
  "/suppliers/expiring-documents",
  "/products",
  "/invoices",
  "/invoices/1",
  "/purchase-orders",
  "/purchase-orders/1",
  "/requests",
  "/requests/1",
  "/approvals",
  "/catalog",
  "/budgets",
  "/approval-settings",
  "/inventory",
  "/deliveries",
  "/reports",
  "/profile",
  "/audit-log",
  "/users",
  "/settings",
  "/settings/email-templates",
  "/payment-runs",
  "/exports",
  "/gdpr",
  "/finance",
];
const PORTAL_PAGES = ["/portal", "/portal/invoices", "/portal/documents", "/portal/password"];

const slug = (route) => (route === "/" ? "home" : route.slice(1).replace(/\//g, "-"));

async function signIn(context, role) {
  const response = await context.request.post(`${API}/auth/demo-login`, { data: { role } });
  if (!response.ok()) throw new Error(`demo-login ${role} failed: ${response.status()}`);
}

async function inspect(page) {
  await page.addScriptTag({ content: AXE_SOURCE });
  return page.evaluate(async () => {
    const result = await window.axe.run(document, { resultTypes: ["violations"] });
    const doc = document.documentElement;
    return {
      violations: result.violations
        .filter((v) => v.impact === "serious" || v.impact === "critical")
        .map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, sample: v.nodes[0]?.target.join(" ") })),
      overflowX: doc.scrollWidth - doc.clientWidth,
    };
  });
}

async function capturePage(browser, job) {
  const context = await browser.newContext({
    viewport: { width: job.viewport.width, height: job.viewport.height },
    colorScheme: job.theme,
    deviceScaleFactor: 1,
  });
  await context.addInitScript(
    ([theme]) => {
      localStorage.setItem("pf-theme", theme);
      localStorage.setItem("procuraflow_has_session", "1");
    },
    [job.theme],
  );
  if (job.role) await signIn(context, job.role);
  const page = await context.newPage();
  const errors = [];
  // A visitor without a session gets a 401 from the silent refresh probe; that is the intended answer.
  const expected = (text) => !job.role && /401 \(Unauthorized\)/.test(text);
  page.on("console", (m) => m.type() === "error" && !expected(m.text()) && errors.push(m.text().slice(0, 200)));
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message.slice(0, 200)}`));
  await page.goto(`${BASE}${job.route}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
  // The app shell scrolls inside a viewport-high container, so a plain full-page shot would cut long pages off.
  // Grow the window by the hidden height of the tallest inner scroller, and a screenshot then shows everything.
  const hidden = await page.evaluate(() =>
    Math.max(
      0,
      ...[...document.querySelectorAll("*")]
        .filter((el) => /auto|scroll/.test(getComputedStyle(el).overflowY) && el.clientHeight > 300)
        .map((el) => el.scrollHeight - el.clientHeight),
    ),
  );
  if (hidden > 0) {
    await page.setViewportSize({
      width: job.viewport.width,
      height: Math.min(job.viewport.height + hidden, MAX_PAGE_HEIGHT),
    });
    await page.waitForTimeout(400);
  }
  const file = path.join(OUT, job.viewport.name, job.theme, `${slug(job.route)}.png`);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  await page.screenshot({ path: file, fullPage: true });
  const found = await inspect(page);
  await context.close();
  return { route: job.route, viewport: job.viewport.name, theme: job.theme, finalUrl: page.url(), errors, ...found };
}

const jobs = [];
for (const viewport of QUICK ? VIEWPORTS.slice(0, 1) : VIEWPORTS) {
  for (const theme of QUICK ? ["light"] : THEMES) {
    for (const route of PUBLIC_PAGES) jobs.push({ viewport, theme, route, role: null });
    for (const route of INTERNAL_PAGES) jobs.push({ viewport, theme, route, role: "admin" });
    for (const route of PORTAL_PAGES) jobs.push({ viewport, theme, route, role: "supplier" });
  }
}

const browser = await chromium.launch();
// Another project's dev server can hold the port; make sure the page really is ProcuraFlow before capturing 200 of it.
{
  const probe = await browser.newPage();
  await probe.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  const title = await probe.title();
  await probe.close();
  if (!/procuraflow/i.test(title)) {
    await browser.close();
    throw new Error(`${BASE} serves "${title}", not ProcuraFlow; check the port`);
  }
}
const report = [];
for (const job of jobs.filter((j) => j.route.includes(ONLY))) {
  try {
    report.push(await capturePage(browser, job));
  } catch (error) {
    report.push({
      route: job.route,
      viewport: job.viewport.name,
      theme: job.theme,
      failure: String(error).slice(0, 300),
    });
  }
}
await browser.close();
fs.mkdirSync(OUT, { recursive: true });
fs.writeFileSync(path.join(OUT, "report.json"), JSON.stringify(report, null, 2));

const bad = report.filter((r) => r.failure || r.violations?.length || r.overflowX > 0 || r.errors?.length);
for (const r of bad) {
  console.log(
    `${r.route} ${r.viewport} ${r.theme}: ${r.failure ?? ""}${r.overflowX > 0 ? ` overflowX=${r.overflowX}` : ""}`,
  );
  for (const v of r.violations ?? []) console.log(`   axe ${v.impact} ${v.id} x${v.nodes} ${v.sample}`);
  for (const e of r.errors ?? []) console.log(`   console ${e}`);
}
console.log(`${report.length} captures, ${bad.length} with findings`);
