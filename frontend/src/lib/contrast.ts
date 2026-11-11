/** WCAG 2.x relative luminance and contrast, used where a colour comes from company settings, not from our tokens. */
const HEX_COLOR = /^#([0-9a-f]{6})$/i;
const LIGHT_TEXT = "#FFFFFF";
const DARK_TEXT = "#0B1220";

function channel(value: number): number {
  const scaled = value / 255;
  return scaled <= 0.03928 ? scaled / 12.92 : ((scaled + 0.055) / 1.055) ** 2.4;
}

/** Relative luminance (0 to 1) of "#RRGGBB", or null when the text is not a six-digit hex colour. */
export function relativeLuminance(hex: string): number | null {
  const match = HEX_COLOR.exec(hex.trim());
  if (!match) return null;
  const value = Number.parseInt(match[1], 16);
  const [red, green, blue] = [(value >> 16) & 255, (value >> 8) & 255, value & 255].map(channel);
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

export function contrastRatio(first: number, second: number): number {
  const [lighter, darker] = first >= second ? [first, second] : [second, first];
  return (lighter + 0.05) / (darker + 0.05);
}

/** White or near-black text, whichever reads better on `background`. An unusable colour gets white. */
export function readableTextOn(background: string): string {
  const luminance = relativeLuminance(background);
  if (luminance === null) return LIGHT_TEXT;
  const dark = relativeLuminance(DARK_TEXT) ?? 0;
  return contrastRatio(luminance, 1) >= contrastRatio(luminance, dark) ? LIGHT_TEXT : DARK_TEXT;
}
