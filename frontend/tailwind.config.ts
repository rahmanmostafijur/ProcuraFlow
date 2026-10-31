import type { Config } from "tailwindcss";

/** A full 50-950 ramp whose steps are CSS variables from src/styles/tokens.css. */
const STEPS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950] as const;
const ramp = (name: string) => Object.fromEntries(STEPS.map((step) => [step, `var(--${name}-${step})`]));
const token = (name: string) => `var(--${name})`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  // Dark applies for the .dark class and for data-theme="dark"; "system" mode sets the class from matchMedia.
  darkMode: ["variant", ["&:is(.dark *)", '&:is([data-theme="dark"] *)']],
  theme: {
    extend: {
      colors: {
        ink: ramp("ink"),
        emerald: ramp("emerald"),
        amber: ramp("amber"),
        red: ramp("red"),
        orange: ramp("orange"),
        blue: ramp("blue"),
        // The brand ramp is emerald; DEFAULT follows the theme (emerald-700 light, emerald-400 dark).
        brand: {
          ...ramp("emerald"),
          DEFAULT: token("brand"),
          hover: token("brand-hover"),
          subtle: token("brand-subtle"),
        },
        bg: token("bg"),
        surface: { DEFAULT: token("surface"), raised: token("surface-raised") },
        border: { DEFAULT: token("border"), strong: token("border-strong") },
        text: { primary: token("text-primary"), secondary: token("text-secondary"), muted: token("text-muted") },
        "on-brand": token("on-brand"),
        "brand-subtle-fg": token("brand-subtle-fg"),
        accent: { DEFAULT: token("accent"), fg: token("on-accent") },
        focus: token("focus"),
        success: { bg: token("success-bg"), fg: token("success-fg") },
        warning: { bg: token("warning-bg"), fg: token("warning-fg") },
        danger: {
          bg: token("danger-bg"),
          fg: token("danger-fg"),
          solid: token("danger-solid"),
          on: token("on-danger-solid"),
        },
        attention: { bg: token("attention-bg"), fg: token("attention-fg") },
        info: { bg: token("info-bg"), fg: token("info-fg") },
      },
      fontFamily: { sans: [token("font-sans")], mono: [token("font-mono")] },
      // Display sizes carry negative tracking so large headings do not look loose.
      fontSize: {
        "display-xl": ["3.5rem", { lineHeight: "3.75rem", letterSpacing: "-0.03em", fontWeight: "800" }],
        "display-lg": ["2.5rem", { lineHeight: "2.75rem", letterSpacing: "-0.025em", fontWeight: "800" }],
        "display-md": ["2rem", { lineHeight: "2.375rem", letterSpacing: "-0.02em", fontWeight: "700" }],
        "display-sm": ["1.5rem", { lineHeight: "1.875rem", letterSpacing: "-0.015em", fontWeight: "700" }],
        title: ["1.125rem", { lineHeight: "1.625rem", letterSpacing: "-0.005em", fontWeight: "600" }],
        body: ["0.9375rem", { lineHeight: "1.5rem" }],
        cell: ["0.8125rem", { lineHeight: "1.25rem" }],
        caption: ["0.75rem", { lineHeight: "1rem", letterSpacing: "0.04em", fontWeight: "600" }],
      },
      spacing: { 18: "4.5rem", 22: "5.5rem" },
      borderRadius: {
        control: token("radius-control"),
        card: token("radius-card"),
        overlay: token("radius-overlay"),
        hero: token("radius-hero"),
      },
      boxShadow: { "elev-1": token("shadow-1"), "elev-2": token("shadow-2"), "elev-3": token("shadow-3") },
      transitionDuration: { fast: token("duration-fast"), base: token("duration-base"), slow: token("duration-slow") },
      transitionTimingFunction: { standard: token("ease-standard") },
    },
  },
  plugins: [],
} satisfies Config;
