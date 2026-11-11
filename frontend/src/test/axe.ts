import axe from "axe-core";

const BLOCKING_IMPACTS = new Set(["serious", "critical"]);

/**
 * Runs axe over `container` and returns one line per serious or critical violation (empty when clean).
 * Colour contrast needs real layout and colours, so jsdom cannot judge it; the browser QA run
 * (scripts/qa-capture.mjs, logged in DESIGN_REVIEW.md) covers contrast in both themes.
 */
export async function blockingViolations(container: Element): Promise<string[]> {
  const result = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
  return result.violations
    .filter((violation) => violation.impact && BLOCKING_IMPACTS.has(violation.impact))
    .map((violation) => `${violation.impact} ${violation.id}: ${violation.nodes[0]?.target.join(" ") ?? ""}`);
}
