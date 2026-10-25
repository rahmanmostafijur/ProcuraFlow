import { useEffect } from "react";

const BRAND_COLOR_VARIABLE = "--company-brand";

/** Exposes the company's colour to CSS so the header, sign-in panel and logo tile follow the branding. */
export function useApplyBrandColor(color: string | undefined): void {
  useEffect(() => {
    if (color) document.documentElement.style.setProperty(BRAND_COLOR_VARIABLE, color);
  }, [color]);
}
