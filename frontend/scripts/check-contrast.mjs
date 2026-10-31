/* global console, process, URL */
// Verifies WCAG AA for every text/background and UI pairing used by the semantic tokens, in both themes.
// Reads the real values from src/styles/tokens.css so the check cannot drift from what ships. No dependencies.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const css = readFileSync(fileURLToPath(new URL("../src/styles/tokens.css", import.meta.url)), "utf8");

const TEXT = 4.5; // normal text
const UI = 3; // large text, focus rings, control borders, icons

/** Pull "--name: value;" declarations out of a block body. */
function declarations(body) {
  const vars = {};
  for (const [, name, value] of body.matchAll(/(--[\w-]+):\s*([^;]+);/g)) vars[name] = value.trim();
  return vars;
}

/** The text between the first "{" after `header` and its matching "}". */
function block(header) {
  const start = css.indexOf(header);
  if (start < 0) throw new Error(`tokens.css: missing block "${header}"`);
  const open = css.indexOf("{", start);
  let depth = 0;
  for (let i = open; i < css.length; i++) {
    if (css[i] === "{") depth++;
    if (css[i] === "}" && --depth === 0) return css.slice(open + 1, i);
  }
  throw new Error(`tokens.css: unbalanced block "${header}"`);
}

const raw = declarations(block(":root {"));
const light = { ...raw, ...declarations(block(":root {")) };
const dark = { ...raw, ...declarations(block(':root[data-theme="dark"] {')) };
const systemDark = { ...raw, ...declarations(block(":root:not([data-theme]) {")) };

function resolve(vars, name, seen = []) {
  let value = vars[name];
  if (value === undefined) throw new Error(`Unknown token ${name}`);
  const ref = /^var\((--[\w-]+)\)$/.exec(value);
  if (!ref) return value;
  if (seen.includes(ref[1])) throw new Error(`Token cycle at ${name}`);
  return resolve(vars, ref[1], [...seen, name]);
}

function luminance(hex) {
  const n = Number.parseInt(hex.replace("#", ""), 16);
  const channel = (v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel((n >> 16) & 255) + 0.7152 * channel((n >> 8) & 255) + 0.0722 * channel(n & 255);
}

function ratio(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

// [foreground token, background token, minimum ratio, what it is]
const PAIRINGS = [
  ["--text-primary", "--bg", TEXT, "Body text on page"],
  ["--text-primary", "--surface", TEXT, "Body text on card"],
  ["--text-primary", "--surface-raised", TEXT, "Body text on modal/menu"],
  ["--text-secondary", "--bg", TEXT, "Secondary text on page"],
  ["--text-secondary", "--surface", TEXT, "Secondary text on card"],
  ["--text-secondary", "--surface-raised", TEXT, "Secondary text on modal/menu"],
  ["--text-muted", "--bg", TEXT, "Muted text/placeholder on page"],
  ["--text-muted", "--surface", TEXT, "Muted text/placeholder on card"],
  ["--text-muted", "--surface-raised", TEXT, "Muted text on modal/menu"],
  ["--brand", "--bg", TEXT, "Link / brand text on page"],
  ["--brand", "--surface", TEXT, "Link / brand text on card"],
  ["--brand", "--brand-subtle", TEXT, "Link on brand tint"],
  ["--brand-hover", "--surface", TEXT, "Link hover on card"],
  ["--on-brand", "--brand", TEXT, "Primary button label"],
  ["--on-brand", "--brand-hover", TEXT, "Primary button label, hover"],
  ["--brand-subtle-fg", "--brand-subtle", TEXT, "Selected nav / brand tint label"],
  ["--on-accent", "--accent", TEXT, "Accent button label"],
  ["--on-danger-solid", "--danger-solid", TEXT, "Danger button label"],
  ["--success-fg", "--success-bg", TEXT, "Success badge"],
  ["--warning-fg", "--warning-bg", TEXT, "Warning badge"],
  ["--danger-fg", "--danger-bg", TEXT, "Danger badge"],
  ["--attention-fg", "--attention-bg", TEXT, "Attention badge"],
  ["--info-fg", "--info-bg", TEXT, "Info badge"],
  ["--focus", "--bg", UI, "Focus ring on page"],
  ["--focus", "--surface", UI, "Focus ring on card"],
  ["--focus", "--surface-raised", UI, "Focus ring on modal/menu"],
  ["--border-strong", "--surface", UI, "Input / control border on card"],
  ["--border-strong", "--bg", UI, "Control border on page"],
];

// The two dark blocks must be identical, otherwise "system" and explicit dark would render differently.
const drift = Object.keys({ ...dark, ...systemDark }).filter((k) => resolve(dark, k) !== resolve(systemDark, k));

let failures = drift.map((k) => `dark blocks differ on ${k}`);
console.log("Theme  Foreground          Background          Ratio  Min   Result  Pairing");
for (const [themeName, vars] of [
  ["light", light],
  ["dark", dark],
]) {
  for (const [fg, bg, min, label] of PAIRINGS) {
    const value = ratio(resolve(vars, fg), resolve(vars, bg));
    const ok = value >= min;
    if (!ok) failures.push(`${themeName}: ${fg} on ${bg} is ${value.toFixed(2)}:1, needs ${min}:1 (${label})`);
    console.log(
      `${themeName.padEnd(6)} ${fg.padEnd(19)} ${bg.padEnd(19)} ${value.toFixed(2).padStart(5)}  ${String(min).padEnd(4)}  ${ok ? "pass" : "FAIL"}    ${label}`,
    );
  }
}

if (failures.length > 0) {
  console.error(`\n${failures.length} problem(s):\n${failures.join("\n")}`);
  process.exit(1);
}
console.log(`\nAll ${PAIRINGS.length * 2} pairings meet WCAG AA and the dark blocks match.`);
